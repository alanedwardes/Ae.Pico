import asyncio

class DisplaySwitcherController:
    def __init__(self, switcher):
        self.switcher = switcher

    CREATION_PRIORITY = 2
    
    def create(provider):
        switcher = provider.get('displayswitcher.DisplaySwitcher')
        management = provider.get('management.ManagementServer')
        
        if switcher is None or management is None:
            return
            
        controller = DisplaySwitcherController(switcher)
        management.controllers.append(controller)

    async def start(self):
        # Component exists only to register the controller
        await asyncio.Event().wait()

    def route(self, method, path):
        if method != b'POST':
            return False
            
        return path == b'/displayswitcher/next' or \
               path == b'/displayswitcher/prev' or \
               path == b'/displayswitcher/pause'

    def widget(self):
        return b'''
        <p style="text-align: center;">
            <form action="/displayswitcher/prev" method="post">
                <button>&lt; Prev</button>
            </form>
            <form action="/displayswitcher/pause" method="post">
                <button>Pause 1h</button>
            </form>
            <form action="/displayswitcher/next" method="post">
                <button>Next &gt;</button>
            </form>
        </p>
        '''

    async def serve(self, method, path, headers, reader, writer):
        # Read content length to consume body if any (standard practice even if unused)
        content_length = int(headers.get(b'content-length', '0'))
        if content_length > 0:
            await reader.readexactly(content_length)

        if path == b'/displayswitcher/next':
            self.switcher.next()
        elif path == b'/displayswitcher/prev':
            self.switcher.prev()
        elif path == b'/displayswitcher/pause':
            self.switcher.pause(3600)

        # Redirect back to home page
        writer.write(b'HTTP/1.0 302 Found\r\n')
        writer.write(b'Location: /\r\n')
        writer.write(b'Content-Length: 0\r\n')
        writer.write(b'\r\n')
        await writer.drain()
