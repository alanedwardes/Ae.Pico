import asyncio
from drawing import Drawing
from framebuffercontroller import FramebufferController


def _path_for_service_key(service_key):
    """'weatherdisplay.WeatherDisplay' -> b'/weather'"""
    class_name = service_key.split('.')[-1]
    if class_name.endswith('Display'):
        name = class_name[:-len('Display')]
    else:
        name = class_name
    return ('/' + name.lower()).encode()


class DisplayController:
    def __init__(self, display, provider, service_keys):
        self.display = display
        self.provider = provider
        self._routes = {_path_for_service_key(k): k for k in service_keys}

    CREATION_PRIORITY = 2

    def create(provider):
        display = provider.get('display')
        management = provider.get('management.ManagementServer')
        config = provider.get('config', {})
        service_keys = config.get('switcher', {}).get('services', [])

        if display is None or management is None or not service_keys:
            return

        controller = DisplayController(display, provider, service_keys)
        management.controllers.append(controller)

    async def start(self):
        await asyncio.Event().wait()

    def route(self, method, path):
        return method == b'GET' and path in self._routes

    def widget(self):
        parts = [b'<p>Displays: ']
        for path in sorted(self._routes.keys()):
            parts.append(b'<a href="' + path + b'">' + path[1:] + b'</a> ')
        parts.append(b'</p>')
        return b''.join(parts)

    async def serve(self, method, path, headers, reader, writer):
        service_key = self._routes.get(path)
        service = self.provider.get(service_key) if service_key else None

        if service is None or not hasattr(service, 'update'):
            writer.write(b'HTTP/1.0 404 Not Found\r\nContent-Length: 0\r\n\r\n')
            await writer.drain()
            return

        width, height = self.display.get_bounds()
        start_y = getattr(service, 'start_y', 0)
        render_height = height - start_y

        temp_drawing = Drawing(width, render_height, self.display.color_mode)

        original_display = service.display
        original_start_y = getattr(service, 'start_y', None)
        original_display_height = getattr(service, 'display_height', None)

        service.display = temp_drawing
        if original_start_y is not None:
            service.start_y = 0
        if original_display_height is not None:
            service.display_height = render_height

        try:
            await service.update()
        finally:
            service.display = original_display
            if original_start_y is not None:
                service.start_y = original_start_y
            if original_display_height is not None:
                service.display_height = original_display_height

        await FramebufferController(temp_drawing).serve(method, path, headers, reader, writer)
