import asyncio
import utime
import gc
import socket

from httpstream import HttpRequest, stream_reader_to_buffer

class RemoteDisplay:
    def __init__(self, display, url, refresh_period=1, start_offset=0):
        self.display = display
        self.url = url
        self.refresh_period = refresh_period
        self.start_offset = start_offset
        self.is_active = False

        self.display_width, self.display_height = self.display.get_bounds()

        # Pre-allocate HTTP request helper
        self._http_request = HttpRequest(url)

    CREATION_PRIORITY = 1
    def create(provider):
        config = provider['config']['remote']
        return RemoteDisplay(
            provider['display'],
            config['url'],
            config.get('refresh_period', 1),
            config.get('start_offset', 0)
        )
       
    async def start(self):
        await asyncio.Event().wait()

    async def activate(self, new_active):
        self.is_active = new_active
        while self.is_active:
            await self.update()

    async def update(self):
        await asyncio.wait_for(self.__update(), timeout=5)

    async def __update(self):
        # Use unified HTTP request helper
        reader, writer = await self._http_request.get()

        try:
            # Check if still active before reading into framebuffer
            if not self.is_active:
                return

            # Get direct access to the display framebuffer with offset
            framebuffer = memoryview(self.display)[self.start_offset:]

            # Stream data directly into framebuffer using shared method
            await stream_reader_to_buffer(reader, framebuffer)

            # Tell display to update the screen (only the region we wrote to)
            # start_offset is in bytes, RGB565 uses 2 bytes per pixel
            y_offset = (self.start_offset // 2) // self.display_width
            height = self.display_height - y_offset
            self.display.update((0, y_offset, self.display_width, height))
        finally:
            writer.close()
            await writer.wait_closed()

            # Clean up after HTTP request
            gc.collect()
