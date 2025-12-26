import asyncio
import utime
import socket

try:
    ThreadSafeFlag = asyncio.ThreadSafeFlag
except AttributeError:
    from threadsafeflag import ThreadSafeFlag

from httpstream import parse_url, stream_reader_to_buffer

class RemoteDisplay:
    def __init__(self, display, url, refresh_period=1, start_offset=0):
        self.display = display
        self.url = url
        self.refresh_period = refresh_period
        self.start_offset = start_offset
        self.is_active = True
        self.update_flag = ThreadSafeFlag()
        
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
                # Wait for either the refresh period or an activation change
                try:
                    await asyncio.wait_for(self.update_flag.wait(), self.refresh_period)
                except asyncio.TimeoutError:
                    pass
            else:
                # Wait for activation change
                await self.update_flag.wait()
    
    def should_activate(self):
        return True

    def activate(self, new_active):
        self.is_active = new_active
        if self.is_active:
            # Immediately trigger an update
            self.update_flag.set()

    def update(self):
        # This class doesn't use update() since it streams continuously
        # The main loop in start() handles the refresh timing
        pass
    
    
    async def fetch_framebuffer(self):
        start_fetch_ms = utime.ticks_ms()
        await self.__fetch_framebuffer()
        fetch_time_ms = utime.ticks_diff(utime.ticks_ms(), start_fetch_ms)
        print(f"RemoteDisplay: {fetch_time_ms}ms")

    async def __fetch_framebuffer(self):
        try:
            url = self.url
            uri = parse_url(url)
            host, port, path, secure = uri.hostname, uri.port, uri.path, uri.secure
            
            reader, writer = await asyncio.open_connection(host, port, ssl=secure)
            
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
            
            # Check if still active before reading into framebuffer
            if not self.is_active:
                writer.close()
                await writer.wait_closed()
                return
            
            # Get direct access to the display framebuffer with offset
            framebuffer = memoryview(self.display)[self.start_offset:]
            
            # Stream data directly into framebuffer using shared method
            await stream_reader_to_buffer(reader, framebuffer)
            
            writer.close()
            await writer.wait_closed()

            # Tell display to update the screen (only the region we wrote to)
            # start_offset is in bytes, RGB565 uses 2 bytes per pixel
            y_offset = (self.start_offset // 2) // self.display_width
            height = self.display_height - y_offset
            self.display.update((0, y_offset, self.display_width, height))
                
        except Exception as e:
            print(f"Error streaming framebuffer data: {e}")
