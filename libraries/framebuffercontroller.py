import asyncio

class FramebufferController:
    def __init__(self, display):
        self.display = display

    CREATION_PRIORITY = 1
    def create(provider):
        display = provider.get('display')
        management = provider.get('management.ManagementServer')
        if display is None or management is None:
            return
        
        controller = FramebufferController(display)
        management.controllers.append(controller)

    async def start(self):
        # Component exists only to register the controller
        await asyncio.Event().wait()

    # Controller interface
    def route(self, method, path):
        return method == b'GET' and path == b'/framebuffer'

    async def serve(self, method, path, headers, reader, writer):
        # Raw, continuous RGB565 stream (little-endian). No Content-Length; keep-alive until client closes.
        writer.write(b'HTTP/1.0 200 OK\r\n')
        writer.write(b'Content-Type: application/octet-stream\r\n')
        writer.write(b'\r\n')

        try:
            while True:
                mv = memoryview(self.display)
                total = len(mv)
                offset = 0
                chunk = 8192
                while offset < total:
                    end = offset + chunk
                    writer.write(mv[offset:end])
                    offset = end
                    await writer.drain()
                await asyncio.sleep(1)
        except Exception:
            # Client closed or write failed; end stream
            pass
