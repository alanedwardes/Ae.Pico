import gc
import re
import asyncio
import os
import hashlib
from collections import namedtuple

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

URL_RE = re.compile(r'(http|https)://([A-Za-z0-9-\.]+)(?:\:([0-9]+))?(.+)?')
URI = namedtuple('URI', ('hostname', 'port', 'path'))

def urlparse(uri):
    match = URL_RE.match(uri)
    if match:
        protocol = match.group(1)
        host = match.group(2)
        port = match.group(3)
        path = match.group(4)

        if protocol == 'https':
            if port is None:
                port = 443
        elif protocol == 'http':
            if port is None:
                port = 80
        else:
            raise ValueError('Scheme {} is invalid'.format(protocol))

        return URI(host.encode('ascii'), int(port), b'/' if path is None else path.encode('utf-8'))

class ManifestDownloader:
    """Handles downloading and parsing manifest files, and downloading individual files."""
    
    async def get_manifest(self, manifest_url):
        """Download and parse a manifest file, returning a list of (filename, expected_hash, download_url) tuples."""
        # Parse the manifest URL to get the base folder
        manifest_uri = urlparse(manifest_url)
        manifest_path = manifest_uri.path.decode('utf-8')
        
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
                download_url = f"http{'s' if manifest_uri.port == 443 else ''}://{manifest_uri.hostname.decode('ascii')}:{manifest_uri.port}{base_folder}/{filename}"
                
                file_list.append((filename, expected_hash, download_url))
        
        return file_list
    
    async def download_manifest_item(self, manifest_item, destination_folder):
        """Download a single item from a manifest item tuple (filename, expected_hash, download_url).
        Returns a tuple of (filename, status, message) where status is 'updated', 'skipped', or 'error'."""
        filename, expected_hash, download_url = manifest_item
        
        # Check if file already exists and has the same hash
        destination_path = path_join(destination_folder, filename)
        
        try:
            # Check if file exists and verify its hash
            if os.path.exists(destination_path):
                actual_hash = self._calculate_sha256(destination_path)
                if actual_hash == expected_hash:
                    # File exists and hash matches, no need to download
                    return filename, 'skipped', f'File {filename} is up to date (hash matches)'
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
        uri = urlparse(url)
        
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
        uri = urlparse(url)
        
        path_parts = uri.path.decode('utf-8').split('/')
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
        writer.write(b'GET %s HTTP/1.0\r\n' % uri.path)
        writer.write(b'Host: %s\r\n' % uri.hostname)
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
                writer.write(b'<form action="/remoteupdate/bundle/%i" method="post">' % i)
                writer.write(b'<input type="hidden" name="action" value="update"/>')
                writer.write(b'<button type="submit">Update This Bundle</button>')
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
            
            completion_msg = '<div style="color: Highlight; margin-top: 20px;"><strong>Bundle update completed successfully!</strong></div>'
            writer.write(completion_msg.encode('utf-8'))
            await writer.drain()
            
        except Exception as e:
            error_msg = f'<div style="color: Mark;"><strong>Bundle update failed: {str(e)}</strong></div>'
            writer.write(error_msg.encode('utf-8'))
            await writer.drain()
