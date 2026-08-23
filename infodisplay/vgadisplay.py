import asyncio
from vga import VGA, VGA_STATS_FIELDS
from drawing import Drawing

DEFAULT_WIDTH = 320
DEFAULT_HEIGHT = 240


class VGADisplay:
    def __init__(self, vga, drawing):
        self.vga = vga
        self.drawing = drawing

    def create(provider):
        config = provider['config'].get('display', {})

        width = config.get('width', DEFAULT_WIDTH)
        height = config.get('height', DEFAULT_HEIGHT)
        mode = config.get('mode', 'RGB565')
        hsync_pin = config.get('hsync_pin', 16)
        color_base_pin = config.get('color_base_pin', 0)
        vsync_pin = config.get('vsync_pin', 17)

        drawing = Drawing(width, height, color_mode=mode)

        vga = VGA(
            drawing.framebuffer,
            width,
            height,
            hsync_pin=hsync_pin,
            color_base_pin=color_base_pin,
            vsync_pin=vsync_pin,
            source_color_mode=mode,
            timing=config.get('timing'),
            pixel_clock=config.get('pixel_clock'),
            h_sync=config.get('h_sync'),
            h_back_porch=config.get('h_back_porch'),
            h_active=config.get('h_active'),
            h_front_porch=config.get('h_front_porch'),
            v_pulse=config.get('v_pulse'),
            v_back_porch=config.get('v_back_porch'),
            v_active=config.get('v_active'),
            v_front_porch=config.get('v_front_porch'),
            sync_positive=config.get('sync_positive'),
            h_sync_max_deviation=config.get('h_sync_max_deviation'),
        )
        vga.start()
        drawing.set_driver(vga)

        provider['display'] = drawing
        return VGADisplay(vga, drawing)

    async def start(self):
        await asyncio.Event().wait()


class VgaStatsController:
    def __init__(self, vga):
        self.vga = vga

    CREATION_PRIORITY = 1
    def create(provider):
        vga_display = provider.get('vgadisplay.VGADisplay')
        management = provider.get('management.ManagementServer')
        if vga_display is None or management is None:
            return

        controller = VgaStatsController(vga_display.vga)
        management.controllers.append(controller)
        return controller

    async def start(self):
        await asyncio.Event().wait()

    def route(self, method, path):
        return method == b'GET' and path == b'/vgastats'

    def widget(self):
        return b' <a href="vgastats">VGA Stats</a>'

    async def serve(self, method, path, headers, reader, writer):
        stats = self.vga.stats()

        writer.write(b'HTTP/1.0 200 OK\r\n')
        writer.write(b'Content-Type: text/html; charset=utf-8\r\n')
        writer.write(b'Cache-Control: no-cache\r\n')
        writer.write(b'Connection: close\r\n')
        writer.write(b'\r\n')
        writer.write(b'<meta http-equiv="refresh" content="1">')
        writer.write(b'<style>form{display:inline;}body{background-color:Canvas;color:CanvasText;color-scheme:light dark;font-family:sans-serif;}</style>')
        writer.write(b'<h1>VGA Stats</h1>')

        if stats is None:
            writer.write(b'<p>VGA has not started.</p>')
        else:
            writer.write(b'<table><tbody>')
            for name, value in zip(VGA_STATS_FIELDS, stats):
                writer.write(b'<tr><td>%s</td><td>%i</td></tr>' % (name.encode('utf-8'), value))
            writer.write(b'</tbody></table>')

        writer.write(b'<p><a href="/">Back</a></p>')
        await writer.drain()
        writer.close()
        await writer.wait_closed()
