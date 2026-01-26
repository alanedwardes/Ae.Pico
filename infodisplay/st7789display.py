import asyncio
from machine import SPI, Pin
from st7789 import ST7789, LANDSCAPE
from drawing import Drawing

# Default display dimensions
DEFAULT_WIDTH = 320
DEFAULT_HEIGHT = 240

class ST7789Display:
    def __init__(self, st, drawing):
        self.st = st
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

        spi = SPI(0, baudrate=40000000, polarity=0, phase=0, sck=Pin(18), mosi=Pin(19))
        dc = Pin(16, Pin.OUT, value=0)
        cs = Pin(17, Pin.OUT, value=1)
        backlight = Pin(20, Pin.OUT, value=1)

        st = ST7789(
            spi,
            cs=cs,
            dc=dc,
            backlight=backlight,
            height=display_height,
            width=display_width,
            disp_mode=LANDSCAPE,
            display=(0, 0, 1, 0, True),
            scale=scale,
        )

        # Optional rotation from config
        rotation = config.get('rotate', 0)  # degrees: 0/90/180/270
        st.set_rotation_degrees(int(rotation))

        # Drawing uses reduced framebuffer dimensions
        drawing = Drawing(fb_width, fb_height)
        drawing.set_driver(st)

        provider['display'] = drawing
        return ST7789Display(st, drawing)

    async def start(self):
        await asyncio.Event().wait()
