import asyncio
import gc

from httpstream import HttpRequest

class StaticDisplay:
    def __init__(self, display, url, start_offset=0):
        self.display = display
        self.url = url
        self.start_offset = start_offset

        self.display_width, self.display_height = self.display.get_bounds()

        # Pre-allocate HTTP request helper
        self._http_request = HttpRequest(url)

    CREATION_PRIORITY = 1
    def create(provider):
        config = provider['config']['static']
        # Support both simple URL string and config dict
        if isinstance(config, str):
            url = config
            start_offset = 0
        else:
            url = config['url']
            start_offset = config.get('start_offset', 0)
            
        return StaticDisplay(
            provider['display'],
            url,
            start_offset
        )
       
    async def start(self):
        await asyncio.Event().wait()

    async def activate(self):
        # Update once, then wait forever
        await self.update()
        await asyncio.Event().wait()

    async def update(self):
        await asyncio.wait_for(self.__update(), timeout=30)

    async def __update(self):
        # Use unified HTTP request helper
        async with self._http_request.get_scoped() as (reader, writer):
            # Tell display to update the screen (only the region we wrote to)
            # start_offset is in bytes, RGB565 uses 2 bytes per pixel
            # y_offset = (self.start_offset // 2) // self.display_width
            # height = self.display_height - y_offset
            # self.display.update((0, y_offset, self.display_width, height))

            y_offset = (self.start_offset // 2) // self.display_width
            height = self.display_height - y_offset
            await self.display.load_stream(reader, 0, y_offset, self.display_width, height)

            # Clean up after HTTP request
            gc.collect()
