import asyncio
from vga import VGA
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
