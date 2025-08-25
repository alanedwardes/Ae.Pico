import asyncio
import utime
import socket
import re

URL_RE = re.compile(r'(http|https)://([A-Za-z0-9-\.]+)(?:\:([0-9]+))?(.+)?')

class RemoteDisplay:
    def __init__(self, display, url, refresh_period=1, start_offset=0):
        self.display = display
        self.url = url
        self.refresh_period = refresh_period
        self.start_offset = start_offset
        self.is_active = True
        
        self.display_width, self.display_height = self.display.get_bounds()
        
    CREATION_PRIORITY = 1
    def create(provider):
        config = provider['config']['remote']
        return RemoteDisplay(
            provider['display'],
            config['url'],
            config.get('refresh_period', 1),
            config.get('start_offset', 0)
        )
    
    def entity_updated(self, entity_id, entity):
        pass
    
    async def start(self):
        while True:
            if self.is_active:
                await self.fetch_framebuffer()
            await asyncio.sleep(self.refresh_period)
    
    def should_activate(self):
        return True

    def activate(self, new_active):
        self.is_active = new_active
        if self.is_active:
            # Don't call update() here - let the main loop handle it
            pass

    def update(self):
        # This class doesn't use update() since it streams continuously
        # The main loop in start() handles the refresh timing
        pass
    
    def parse_url(self, url):
        match = URL_RE.match(url)
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

            return (host, int(port), path if path else '/', protocol == 'https')
        raise ValueError('Invalid URL format')
    
    async def fetch_framebuffer(self):
        start_fetch_ms = utime.ticks_ms()
        await self.__fetch_framebuffer()
        fetch_time_ms = utime.ticks_diff(utime.ticks_ms(), start_fetch_ms)
        print(f"RemoteDisplay: {fetch_time_ms}ms")

    async def __fetch_framebuffer(self):
        try:
            url = self.url
            host, port, path, use_ssl = self.parse_url(url)
            
            reader, writer = await asyncio.open_connection(host, port, ssl=use_ssl)
            
            # Write HTTP request
            writer.write(f'GET {path} HTTP/1.0\r\n'.encode('utf-8'))
            writer.write(f'Host: {host}\r\n'.encode('utf-8'))
            writer.write(b'\r\n')
            await writer.drain()
            
            # Read response status
            line = await reader.readline()
            status = line.split(b' ', 2)
            status_code = int(status[1])
            
            if status_code != 200:
                print(f"Failed to fetch framebuffer data: HTTP {status_code}")
                writer.close()
                await writer.wait_closed()
                return
            
            # Skip headers
            while True:
                line = await reader.readline()
                if line == b'\r\n':
                    break
            
            # Get direct access to the display framebuffer with offset
            framebuffer = memoryview(self.display)[self.start_offset:]
            
            # Stream data directly into framebuffer - read until no more data
            bytes_read = 0
            if hasattr(reader, 'readinto'):
                # MicroPython - keep reading chunks until no more data
                while bytes_read < len(framebuffer):
                    remaining_buffer = framebuffer[bytes_read:]
                    chunk_bytes = await reader.readinto(remaining_buffer)
                    if chunk_bytes is None or chunk_bytes == 0:
                        break
                    bytes_read += chunk_bytes
            else:
                # CPython - keep reading until no more data
                while bytes_read < len(framebuffer):
                    chunk = await reader.read(len(framebuffer) - bytes_read)
                    if not chunk:
                        break
                    chunk_len = len(chunk)
                    framebuffer[bytes_read:bytes_read + chunk_len] = chunk
                    bytes_read += chunk_len
            writer.close()
            await writer.wait_closed()
            
            # Tell display to update the screen
            self.display.update()
                
        except Exception as e:
            print(f"Error streaming framebuffer data: {e}")
