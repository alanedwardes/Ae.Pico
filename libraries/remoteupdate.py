import gc
import asyncio
import os
import hashlib
from httpstream import parse_url

try:
    from micropython import const
    IS_MICROPYTHON = True
except ImportError:
    IS_MICROPYTHON = False

def parse_form(form):
    data = {}
    for item in form.split(b'&'):
        if not item:
            continue
        item = item.replace(b'+', b' ')
        parts = item.split(b'=')
        if len(parts) == 2:
            data[parts[0]] = parts[1]
    return data

def makedirs(path, exist_ok=False):
    parts = path.split('/')
    current = ''
    for part in parts:
        if part:
            current = current + '/' + part if current else part
            try:
                os.stat(current)
            except OSError:
                try:
                    os.mkdir(current)
                except OSError as e:
                    if not exist_ok or e.args[0] != 17:  # 17 is EEXIST
                        raise

def path_join(*paths):
    filtered_paths = [p for p in paths if p]
    if not filtered_paths:
        return ''
    
    result = '/'.join(filtered_paths)

    while '//' in result:
        result = result.replace('//', '/')
    return result


class ManifestDownloader:
    """Handles downloading and parsing manifest files, and downloading individual files."""
    
    async def get_manifest(self, manifest_url):
        """Download and parse a manifest file, returning a list of (filename, expected_hash, download_url) tuples."""
        # Parse the manifest URL to get the base folder
        manifest_uri = parse_url(manifest_url)
        manifest_path = manifest_uri.path
        
        # Extract the base folder (everything before the filename)
        path_parts = manifest_path.split('/')
        base_folder = '/'.join(path_parts[:-1])  # Remove the manifest.txt filename
        
        # Download the manifest file first
        manifest_content = await self._download_content(manifest_url)
        
        # Parse the manifest to get file list with hashes
        file_list = []
        for line in manifest_content.split('\n'):
            line = line.strip()
            if line and not line.startswith('#'):  # Skip empty lines and comments
                parts = line.split()
                if len(parts) != 2:
                    raise ValueError(f"Invalid manifest line format: {line}. Expected 'filename sha256hash'")
                filename, expected_hash = parts
                
                # Construct the download URL
                download_url = f"http{'s' if manifest_uri.port == 443 else ''}://{manifest_uri.hostname}:{manifest_uri.port}{base_folder}/{filename}"
                
                file_list.append((filename, expected_hash, download_url))
        
        return file_list
    
    async def download_manifest_item(self, manifest_item, destination_folder):
        """Download a single item from a manifest item tuple (filename, expected_hash, download_url).
        Returns a tuple of (filename, status, message) where status is 'updated', 'skipped', or 'error'."""
        filename, expected_hash, download_url = manifest_item
        
        # Check if file already exists and has the same hash
        destination_path = path_join(destination_folder, filename)
        
        try:
            # Check if file exists and verify its hash (MicroPython compatible)
            try:
                os.stat(destination_path)
                # File exists, check its hash
                actual_hash = self._calculate_sha256(destination_path)
                if actual_hash == expected_hash:
                    # File exists and hash matches, no need to download
                    return filename, 'skipped', f'File {filename} is up to date (hash matches)'
            except OSError:
                # File doesn't exist, proceed with download
                pass
        except (OSError, Exception) as e:
            # If we can't read the file or calculate hash, proceed with download
            pass
        
        # Download the file (either it doesn't exist, hash doesn't match, or we couldn't verify)
        try:
            downloaded_filename = await self.download_file(download_url, destination_folder, expected_hash)
            return downloaded_filename, 'updated', f'File {filename} downloaded and updated'
        except Exception as e:
            return filename, 'error', f'Failed to download {filename}: {str(e)}'
    
    async def _download_content(self, url):
        """Download content from a URL and return it as a string."""
        uri = parse_url(url)
        
        reader, writer = await asyncio.open_connection(
            uri.hostname, 
            uri.port, 
            ssl=uri.port == 443
        )
        
        try:
            self._write_http_request(writer, uri)
            await writer.drain()
            
            await self._ensure_success_status_code(reader)
            await self._skip_headers(reader)
            
            # Read all content
            content = b''
            chunk_size = 512 if IS_MICROPYTHON else 8192
            while True:
                chunk = await reader.read(chunk_size)
                if not chunk:
                    break
                content += chunk
            
            return content.decode('utf-8')
            
        finally:
            writer.close()
            await writer.wait_closed()
    
    async def download_files(self, urls, destination_folder):
        """Legacy method for downloading a list of URLs directly."""
        for url in urls:
            await self.download_file(url, destination_folder, None)
    
    async def download_file(self, url, destination_folder, expected_hash):
        uri = parse_url(url)
        
        path_parts = uri.path.split('/')
        filename = path_parts[-1]
        
        destination_path = path_join(destination_folder, filename)
        
        # Ensure destination folder exists
        try:
            makedirs(destination_folder, exist_ok=True)
        except OSError:
            pass
        
        reader, writer = await asyncio.open_connection(
            uri.hostname, 
            uri.port, 
            ssl=uri.port == 443
        )
        
        try:
            self._write_http_request(writer, uri)
            await writer.drain()
            
            await self._ensure_success_status_code(reader)
            await self._skip_headers(reader)
            
            await self._download_to_file(reader, destination_path)
            
        finally:
            writer.close()
            await writer.wait_closed()
        
        # Verify hash if expected_hash is provided
        if expected_hash:
            actual_hash = self._calculate_sha256(destination_path)
            if actual_hash != expected_hash:
                raise Exception(f"SHA256 hash mismatch for {filename}. Expected: {expected_hash}, Got: {actual_hash}")
        
        return filename
    
    def _write_http_request(self, writer, uri):
        writer.write(b'GET %s HTTP/1.0\r\n' % uri.path.encode('utf-8'))
        writer.write(b'Host: %s\r\n' % uri.hostname.encode('utf-8'))
        writer.write(b'Connection: close\r\n')
        writer.write(b'\r\n')
    
    async def _ensure_success_status_code(self, reader):
        line = await reader.readline()
        status = line.split(b' ', 2)
        status_code = int(status[1])
        if status_code not in [200, 201]:
            raise Exception(f"HTTP {status_code}: {line.decode('utf-8', errors='ignore')}")
    
    async def _skip_headers(self, reader):
        while True:
            line = await reader.readline()
            if line == b'\r\n':
                break
    
    async def _download_to_file(self, reader, destination_path):
        with open(destination_path, 'wb') as file:
            chunk_size = 512 if IS_MICROPYTHON else 8192
            while True:
                chunk = await reader.read(chunk_size)
                if not chunk:
                    break
                file.write(chunk)
    
    def _calculate_sha256(self, file_path):
        """Calculate SHA256 hash of a file."""
        sha256_hash = hashlib.sha256()
        chunk_size = 512 if IS_MICROPYTHON else 8192
        
        with open(file_path, 'rb') as file:
            while True:
                chunk = file.read(chunk_size)
                if not chunk:
                    break
                sha256_hash.update(chunk)
        
        if IS_MICROPYTHON:
            # MicroPython doesn't have hexdigest(), so convert digest to hex manually
            return ''.join(['{:02x}'.format(b) for b in sha256_hash.digest()])
        else:
            return sha256_hash.hexdigest()

class RemoteUpdate:
    def __init__(self, bundles):
        self.bundles = bundles
        self.downloader = ManifestDownloader()
    
    CREATION_PRIORITY = 1
    def create(provider):
        config = provider['config'].get('remoteupdate', {})
        remote_update = RemoteUpdate(config.get('bundles', []))
        management = provider.get('management.ManagementServer')
        if management:
            management.controllers.append(remote_update)
        return None

    async def start(self):
        """Start the remote update service - runs indefinitely."""
        await asyncio.Event().wait()

    # Web controller interface methods
    def route(self, method, path):
        # Handle both the main remoteupdate page and individual bundle updates
        if path == b'/remoteupdate':
            return True
        # Handle individual bundle updates: /remoteupdate/bundle/{index}
        if path.startswith(b'/remoteupdate/bundle/'):
            try:
                bundle_index = int(path.split(b'/')[-1])
                return 0 <= bundle_index < len(self.bundles)
            except (ValueError, IndexError):
                return False
        # Handle manifest checking: /remoteupdate/check/{index}
        if path.startswith(b'/remoteupdate/check/'):
            try:
                bundle_index = int(path.split(b'/')[-1])
                return 0 <= bundle_index < len(self.bundles)
            except (ValueError, IndexError):
                return False
        return False
    
    async def serve(self, method, path, headers, reader, writer):
        content_length = int(headers.get(b'content-length', '0'))
        form = parse_form(await reader.readexactly(content_length))
        
        writer.write(b'HTTP/1.0 200 OK\r\n')
        writer.write(b'Content-Type: text/html; charset=utf-8\r\n')
        writer.write(b'\r\n')
        writer.write(b'<style>form{display:inline;}body{background-color:Canvas;color:CanvasText;color-scheme:light dark;font-family:sans-serif;}</style>')
        
        # Check if this is an individual bundle update
        if path.startswith(b'/remoteupdate/bundle/'):
            try:
                bundle_index = int(path.split(b'/')[-1])
                if b'action' in form and form[b'action'] == b'update':
                    await self._handle_bundle_update(writer, bundle_index)
                else:
                    await self._show_bundle_interface(writer, bundle_index)
            except (ValueError, IndexError):
                writer.write(b'<h1>Error</h1><p>Invalid bundle index</p><p><a href="/remoteupdate">Back</a></p>')
        elif path.startswith(b'/remoteupdate/check/'):
            try:
                bundle_index = int(path.split(b'/')[-1])
                if b'action' in form and form[b'action'] == b'check':
                    await self._handle_manifest_check(writer, bundle_index)
                else:
                    await self._show_manifest_check_interface(writer, bundle_index)
            except (ValueError, IndexError):
                writer.write(b'<h1>Error</h1><p>Invalid bundle index</p><p><a href="/remoteupdate">Back</a></p>')
        else:
            # Main remoteupdate page
            await self._show_main_interface(writer)
        
        writer.close()
        await writer.wait_closed()
    
    async def _show_main_interface(self, writer):
        """Show the main remote update interface with individual bundle buttons."""
        writer.write(b'<h1>Remote Update</h1>')
        writer.write(b'<p><b>Available Bundles:</b> %i</p>' % len(self.bundles))
        
        if self.bundles:
            writer.write(b'<div style="margin: 20px 0;">')
            for i, bundle in enumerate(self.bundles):
                writer.write(b'<h2>Bundle %i</h2>' % (i + 1))
                writer.write(b'<p><strong>Source:</strong> %s</p>' % bundle[0].encode('utf-8'))
                writer.write(b'<p><strong>Destination:</strong> %s</p>' % bundle[1].encode('utf-8'))
                writer.write(b'<form action="/remoteupdate/bundle/%i" method="post" style="display:inline; margin-right: 10px;">' % i)
                writer.write(b'<input type="hidden" name="action" value="update"/>')
                writer.write(b'<button type="submit">Update This Bundle</button>')
                writer.write(b'</form>')
                writer.write(b'<form action="/remoteupdate/check/%i" method="post" style="display:inline;">' % i)
                writer.write(b'<input type="hidden" name="action" value="check"/>')
                writer.write(b'<button type="submit">Check Manifest</button>')
                writer.write(b'</form>')
            writer.write(b'</div>')
        else:
            writer.write(b'<p>No bundles configured.</p>')
        
        writer.write(b'<p><a href="/">Back to Home</a></p>')
    
    async def _show_bundle_interface(self, writer, bundle_index):
        """Show interface for a specific bundle."""
        bundle = self.bundles[bundle_index]
        writer.write(b'<h1>Bundle %i Update</h1>' % (bundle_index + 1))
        writer.write(b'<p><strong>Source:</strong> %s</p>' % bundle[0].encode('utf-8'))
        writer.write(b'<p><strong>Destination:</strong> %s</p>' % bundle[1].encode('utf-8'))
        writer.write(b'<form action="/remoteupdate/bundle/%i" method="post">' % bundle_index)
        writer.write(b'<input type="hidden" name="action" value="update"/>')
        writer.write(b'<button type="submit">Start Update</button>')
        writer.write(b'</form>')
        writer.write(b'<p><a href="/remoteupdate">Back to Remote Update</a></p>')
    
    async def _show_manifest_check_interface(self, writer, bundle_index):
        """Show interface for manifest checking."""
        bundle = self.bundles[bundle_index]
        writer.write(b'<h1>Bundle %i Manifest Check</h1>' % (bundle_index + 1))
        writer.write(b'<p><strong>Source:</strong> %s</p>' % bundle[0].encode('utf-8'))
        writer.write(b'<p><strong>Destination:</strong> %s</p>' % bundle[1].encode('utf-8'))
        writer.write(b'<form action="/remoteupdate/check/%i" method="post">' % bundle_index)
        writer.write(b'<input type="hidden" name="action" value="check"/>')
        writer.write(b'<button type="submit">Start Manifest Check</button>')
        writer.write(b'</form>')
        writer.write(b'<p><a href="/remoteupdate">Back to Remote Update</a></p>')
    
    async def _handle_manifest_check(self, writer, bundle_index):
        """Handle the manifest checking process for a specific bundle."""
        bundle = self.bundles[bundle_index]
        
        writer.write(b'<h1>Bundle %i Manifest Check</h1>' % (bundle_index + 1))
        writer.write(b'<div id="progress">Starting manifest check...</div>')
        writer.write(b'<p><a href="/remoteupdate">Back to Remote Update</a></p>')
        await writer.drain()
        
        try:
            progress_msg = f'<div>Checking manifest: {bundle[0]}</div>'
            writer.write(progress_msg.encode('utf-8'))
            await writer.drain()
            
            # Get manifest for this bundle
            manifest = await self.downloader.get_manifest(bundle[0])
            
            total_files = len(manifest)
            matching_files = 0
            missing_files = 0
            mismatched_files = 0
            extra_files = 0

            manifest_files = set([item[0] for item in manifest])
            
            for j, item in enumerate(manifest):
                gc.collect()
                filename, expected_hash, download_url = item
                
                progress_msg = f'<div>Checking {filename} ({j+1}/{total_files})...</div>'
                writer.write(progress_msg.encode('utf-8'))
                await writer.drain()
                
                # Check if file exists and verify its hash
                destination_path = path_join(bundle[1], filename)
                
                try:
                    # Check if file exists using os.stat() (MicroPython compatible)
                    try:
                        os.stat(destination_path)
                        # File exists, check its hash
                        actual_hash = self.downloader._calculate_sha256(destination_path)
                        if actual_hash == expected_hash:
                            status_msg = f'<div style="color: Highlight;">✓ {filename} - Hash matches</div>'
                            matching_files += 1
                        else:
                            status_msg = f'<div style="color: Orange;">⚠ {filename} - Hash mismatch (expected: {expected_hash[:8]}..., got: {actual_hash[:8]}...)</div>'
                            mismatched_files += 1
                    except OSError:
                        # File doesn't exist
                        status_msg = f'<div style="color: Mark;">✗ {filename} - File missing</div>'
                        missing_files += 1
                except Exception as e:
                    status_msg = f'<div style="color: Mark;">✗ {filename} - Error checking file: {str(e)}</div>'
                    missing_files += 1
                
                writer.write(status_msg.encode('utf-8'))
                await writer.drain()

            # Scan for extra files not present in the manifest
            try:
                writer.write(b'<div>Scanning for extra files not in manifest...</div>')
                await writer.drain()

                stack = ['']
                while stack:
                    rel_dir = stack.pop()
                    abs_dir = path_join(bundle[1], rel_dir) if rel_dir else bundle[1]
                    try:
                        entries = os.listdir(abs_dir)
                    except OSError:
                        continue

                    for name in entries:
                        child_rel = path_join(rel_dir, name) if rel_dir else name
                        child_abs = path_join(abs_dir, name)
                        if self._is_dir(child_abs):
                            stack.append(child_rel)
                        else:
                            if child_rel not in manifest_files:
                                extra_files += 1
                                status_msg = f'<div style="color: Mark;">• Extra file: {child_rel}</div>'
                                writer.write(status_msg.encode('utf-8'))
                                await writer.drain()
            except Exception as _scan_err:
                err_msg = f'<div style="color: Mark;">Error scanning for extra files: {str(_scan_err)}</div>'
                writer.write(err_msg.encode('utf-8'))
                await writer.drain()
            
            # Summary
            summary_msg = f'''
            <div style="margin-top: 20px; padding: 10px; background-color: Canvas; border: 1px solid CanvasText;">
                <h3>Manifest Check Summary</h3>
                <p><strong>Total files:</strong> {total_files}</p>
                <p style="color: Highlight;"><strong>Matching files:</strong> {matching_files}</p>
                <p style="color: Orange;"><strong>Mismatched files:</strong> {mismatched_files}</p>
                <p style="color: Mark;"><strong>Missing files:</strong> {missing_files}</p>
                <p style="color: Mark;"><strong>Extra files (not in manifest):</strong> {extra_files}</p>
            </div>
            '''
            writer.write(summary_msg.encode('utf-8'))
            await writer.drain()
            
        except Exception as e:
            error_msg = f'<div style="color: Mark;"><strong>Manifest check failed: {str(e)}</strong></div>'
            writer.write(error_msg.encode('utf-8'))
            await writer.drain()
    
    async def _handle_bundle_update(self, writer, bundle_index):
        """Handle the update process for a specific bundle."""
        bundle = self.bundles[bundle_index]
        
        writer.write(b'<h1>Bundle %i Update</h1>' % (bundle_index + 1))
        writer.write(b'<div id="progress">Starting update process...</div>')
        writer.write(b'<p><a href="/remoteupdate">Back to Remote Update</a></p>')
        await writer.drain()
        
        try:
            progress_msg = f'<div>Processing bundle: {bundle[0]}</div>'
            writer.write(progress_msg.encode('utf-8'))
            await writer.drain()
            
            # Get manifest for this bundle
            manifest = await self.downloader.get_manifest(bundle[0])
            
            for j, item in enumerate(manifest):
                gc.collect()
                progress_msg = f'<div>Processing {item[0]} ({j+1}/{len(manifest)})...</div>'
                writer.write(progress_msg.encode('utf-8'))
                await writer.drain()
                
                filename, status, message = await self.downloader.download_manifest_item(item, bundle[1])
                
                if status == 'updated':
                    status_msg = f'<div style="color: Highlight;">✓ {message}</div>'
                elif status == 'skipped':
                    status_msg = f'<div style="color: GrayText;">○ {message}</div>'
                elif status == 'error':
                    status_msg = f'<div style="color: Mark;">✗ {message}</div>'
                
                writer.write(status_msg.encode('utf-8'))
                await writer.drain()
            
            # Cleanup: remove files/dirs not present in manifest
            try:
                writer.write(b'<div>Cleaning up obsolete files...</div>')
                await writer.drain()

                manifest_files = set([item[0] for item in manifest])
                manifest_dirs = set()
                for rel_path in manifest_files:
                    parts = rel_path.split('/')
                    # include all parent directories for each file
                    for i in range(1, len(parts)):
                        manifest_dirs.add('/'.join(parts[:i]))

                await self._cleanup_obsolete_paths(bundle[1], manifest_files, manifest_dirs, writer)

                writer.write(b'<div style="color: Highlight;"><strong>Cleanup complete</strong></div>')
                await writer.drain()
            except Exception as _cleanup_err:
                # Log cleanup error but do not fail the whole update
                err_msg = f'<div style="color: Mark;">Cleanup encountered an error: {str(_cleanup_err)}</div>'
                writer.write(err_msg.encode('utf-8'))
                await writer.drain()
            
            completion_msg = '<div style="color: Highlight; margin-top: 20px;"><strong>Bundle update completed successfully!</strong></div>'
            writer.write(completion_msg.encode('utf-8'))
            await writer.drain()
            
        except Exception as e:
            error_msg = f'<div style="color: Mark;"><strong>Bundle update failed: {str(e)}</strong></div>'
            writer.write(error_msg.encode('utf-8'))
            await writer.drain()

    def _is_dir(self, path):
        try:
            st = os.stat(path)
            mode = st[0] if isinstance(st, (tuple, list)) else getattr(st, 'st_mode', 0)
            return (mode & 0x4000) != 0
        except OSError:
            return False

    async def _cleanup_obsolete_paths(self, root, manifest_files, manifest_dirs, writer):
        """Remove files under root not listed in manifest_files and prune empty directories not in manifest_dirs."""

        async def recurse(rel_path):
            abs_path = path_join(root, rel_path) if rel_path else root
            try:
                entries = os.listdir(abs_path)
            except OSError:
                return

            for name in entries:
                child_rel = path_join(rel_path, name) if rel_path else name
                child_abs = path_join(abs_path, name)
                if self._is_dir(child_abs):
                    await recurse(child_rel)
                else:
                    if child_rel not in manifest_files:
                        try:
                            os.remove(child_abs)
                            msg = f'<div style="color: Mark;">Deleted file: {child_rel}</div>'
                            writer.write(msg.encode('utf-8'))
                            await writer.drain()
                        except OSError:
                            pass

            # After processing children, try to remove directory if empty and not required
            if rel_path:
                try:
                    # Re-list to check if now empty
                    if not os.listdir(abs_path) and rel_path not in manifest_dirs:
                        os.rmdir(abs_path)
                        msg = f'<div style="color: Mark;">Removed empty directory: {rel_path}</div>'
                        writer.write(msg.encode('utf-8'))
                        await writer.drain()
                except OSError:
                    pass

        await recurse('')
