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

    def widget(self):
        return b'<p><img src="/framebuffer" alt="Framebuffer"/></p>'

    async def serve(self, method, path, headers, reader, writer):
        # Screenshot not supported in direct rendering mode
        writer.write(b'HTTP/1.0 501 Not Implemented\r\n')
        writer.write(b'Content-Type: text/plain\r\n')
        writer.write(b'\r\n')
        writer.write(b'Screenshots are not available in direct rendering mode.')
        await writer.drain()
        writer.close()
        await writer.wait_closed()
