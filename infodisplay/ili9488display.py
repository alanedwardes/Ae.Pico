import asyncio
from machine import SPI, Pin
from ili9488 import ILI9488, REFLECT, PORTRAIT, USD
from drawing import Drawing

DEFAULT_WIDTH = 480
DEFAULT_HEIGHT = 320

class ILI9488Display:
    def __init__(self, ili, drawing):
        self.ili = ili
        self.drawing = drawing

    def create(provider):
        config = provider['config'].get('display', {})

        display_width = config.get('width', DEFAULT_WIDTH)
        display_height = config.get('height', DEFAULT_HEIGHT)

        fb_width = display_width
        fb_height = display_height

        spi = SPI(1, baudrate=40_000_000, polarity=0, phase=0, sck=Pin(10), mosi=Pin(11))
        dc = Pin(8, Pin.OUT, value=0)
        cs = Pin(9, Pin.OUT, value=1)
        rst = Pin(15, Pin.OUT, value=1)
        backlight = Pin(13, Pin.OUT, value=1)

        mode = config.get('mode', 'RGB565')

        rotation = int(config.get('rotate', 0))
        rotation_modes = {0: REFLECT, 90: PORTRAIT | REFLECT | USD, 180: REFLECT | USD, 270: PORTRAIT | REFLECT}
        disp_mode = rotation_modes.get(rotation, REFLECT)

        ili = ILI9488(
            spi,
            cs=cs,
            dc=dc,
            rst=rst,
            backlight=backlight,
            height=display_height,
            width=display_width,
            disp_mode=disp_mode,
            display=(0, 0, 1, True, True),
            source_color_mode=mode
        )

        framebuffer = config.get('framebuffer')
        drawing = Drawing(fb_width, fb_height, color_mode=mode, framebuffer=framebuffer)

        from asyncspidriver import AsyncSpiDriver
        driver = AsyncSpiDriver(ili, drawing.framebuffer, fb_width, fb_height)
        driver.start()
        drawing.set_driver(driver)

        ili.set_backlight(1.0)

        provider['display'] = drawing
        return ILI9488Display(ili, drawing)

    async def start(self):
        await asyncio.Event().wait()
