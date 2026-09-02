import asyncio

from httpstream import HttpRequest, stream_reader_to_buffer

class VideoDisplay:
    def __init__(self, display, url, frame_period=1.0, start_offset=0):
        self.display = display
        self.frame_period = frame_period
        self.start_offset = start_offset

        self.display_width, self.display_height = self.display.get_bounds()

        self._http_request = HttpRequest(url)

    CREATION_PRIORITY = 1

    def create(provider):
        display = provider['display']
        y_separator = provider['config']['display'].get('y_separator', 70)
        start_offset = y_separator * display.width * display.bytes_per_pixel

        for cfg in provider['config'].get('video', []):
            instance = VideoDisplay(
                display,
                cfg['url'],
                cfg.get('frame_period', 1.0),
                start_offset
            )
            provider['video.%s' % cfg['name']] = instance

        remote_cfg = provider['config'].get('remote')
        if remote_cfg:
            provider['remotedisplay.RemoteDisplay'] = VideoDisplay(
                display,
                remote_cfg['url'],
                remote_cfg.get('refresh_period', 0.1),
                start_offset
            )

        return None

    async def start(self):
        await asyncio.Event().wait()

    async def activate(self):
        framebuffer = self.display.framebuffer[self.start_offset:]
        chunk = bytearray(min(1024, len(framebuffer)))

        bytes_per_pixel = self.display.bytes_per_pixel
        y_offset = (self.start_offset // bytes_per_pixel) // self.display_width
        height = self.display_height - y_offset

        while True:
            try:
                reader, writer = await self._http_request.get()
            except OSError:
                await asyncio.sleep(self.frame_period)
                continue

            try:
                while True:
                    bytes_read = await stream_reader_to_buffer(reader, framebuffer, chunk)
                    if bytes_read < len(framebuffer):
                        break

                    await asyncio.sleep(self.frame_period)
            except OSError:
                pass
            finally:
                try:
                    writer.close()
                    await writer.wait_closed()
                except OSError:
                    pass
