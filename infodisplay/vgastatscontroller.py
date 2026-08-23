import asyncio
from vga import VGA_STATS_FIELDS

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
