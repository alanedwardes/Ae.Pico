import asyncio
from machine import SPI, Pin
from st7789 import ST7789, LANDSCAPE
from drawing import Drawing

DEFAULT_WIDTH = 320
DEFAULT_HEIGHT = 240

class ST7789Display:
    def __init__(self, st, drawing):
        self.st = st
        self.drawing = drawing

    def create(provider):
        config = provider['config'].get('display', {})

        display_width = config.get('width', DEFAULT_WIDTH)
        display_height = config.get('height', DEFAULT_HEIGHT)

        fb_width = display_width
        fb_height = display_height

        spi = SPI(0, baudrate=40000000, polarity=0, phase=0, sck=Pin(18), mosi=Pin(19))
        dc = Pin(16, Pin.OUT, value=0)
        cs = Pin(17, Pin.OUT, value=1)
        backlight = Pin(20, Pin.OUT, value=1)

        mode = config.get('mode', 'RGB565')

        st = ST7789(
            spi,
            cs=cs,
            dc=dc,
            backlight=backlight,
            height=display_height,
            width=display_width,
            disp_mode=LANDSCAPE,
            display=(0, 0, 1, 0, True),
            source_color_mode=mode,
        )

        rotation = config.get('rotate', 0)
        st.set_rotation_degrees(int(rotation))

        framebuffer = config.get('framebuffer')
        drawing = Drawing(fb_width, fb_height, color_mode=mode, framebuffer=framebuffer)

        from asyncspidriver import AsyncSpiDriver
        driver = AsyncSpiDriver(st, drawing.framebuffer, fb_width, fb_height)
        driver.start()
        drawing.set_driver(driver)

        st.set_backlight(1.0)

        provider['display'] = drawing
        return ST7789Display(st, drawing)

    async def start(self):
        await asyncio.Event().wait()