import asyncio
from machine import SPI, Pin
from ili9488 import ILI9488, REFLECT
from drawing import Drawing

# Default display dimensions
DEFAULT_WIDTH = 480
DEFAULT_HEIGHT = 320

class ILI9488Display:
    def __init__(self, ili, drawing):
        self.ili = ili
        self.drawing = drawing

    def create(provider):
        config = provider['config'].get('display', {})

        # Get configurable dimensions and scale
        display_width = config.get('width', DEFAULT_WIDTH)
        display_height = config.get('height', DEFAULT_HEIGHT)
        scale = config.get('scale', 1)

        # Framebuffer dimensions are display dimensions divided by scale
        fb_width = display_width // scale
        fb_height = display_height // scale

        # Waveshare default SPI init speed for 3.5 display
        spi = SPI(1, baudrate=40_000_000, polarity=0, phase=0, sck=Pin(10), mosi=Pin(11))
        dc = Pin(8, Pin.OUT, value=0)
        cs = Pin(9, Pin.OUT, value=1)
        rst = Pin(15, Pin.OUT, value=1)
        backlight = Pin(13, Pin.OUT, value=1)

        mode = config.get('mode', 'RGB565')

        ili = ILI9488(
            spi,
            cs=cs,
            dc=dc,
            rst=rst,
            backlight=backlight,
            height=display_height,
            width=display_width,
            disp_mode=REFLECT,
            display=(0, 0, 1, True, True),
            scale=scale,
            source_color_mode=mode,
        )

        # Optional rotation from config
        rotation = config.get('rotate', 0)  # degrees: 0/90/180/270
        ili.set_rotation_degrees(int(rotation))

        # Drawing uses reduced framebuffer dimensions
        drawing = Drawing(fb_width, fb_height, color_mode=mode)
        drawing.set_driver(ili)

        ili.set_backlight(1.0)  # Explicitly trigger hardware backlight

        provider['display'] = drawing
        return ILI9488Display(ili, drawing)

    async def start(self):
        await asyncio.Event().wait()
