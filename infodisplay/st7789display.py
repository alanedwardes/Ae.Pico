import asyncio
from machine import SPI, Pin
from st7789 import ST7789, LANDSCAPE
from drawing import Drawing

WIDTH = 320
HEIGHT = 240

class ST7789Display:
    def __init__(self, st, drawing):
        self.st = st
        self.drawing = drawing

    def create(provider):
        config = provider['config'].get('display', {})

        spi = SPI(0, baudrate=40000000, polarity=0, phase=0, sck=Pin(18), mosi=Pin(19))
        dc = Pin(16, Pin.OUT, value=0)
        cs = Pin(17, Pin.OUT, value=1)
        rst = Pin(12, Pin.OUT, value=1)
        backlight = Pin(20, Pin.OUT, value=1)

        st = ST7789(
            spi,
            cs=cs,
            dc=dc,
            rst=rst,
            backlight=backlight,
            height=HEIGHT,
            width=WIDTH,
            disp_mode=LANDSCAPE,
            display=(0, 0, 1, 0, True),
        )

        # Optional rotation from config
        rotation = config.get('rotate', 0)  # degrees: 0/90/180/270
        st.set_rotation_degrees(int(rotation))

        drawing = Drawing(WIDTH, HEIGHT)

        # Pass the hardware driver directly; Drawing will call st.render()
        drawing.set_driver(st)

        provider['display'] = drawing
        return ST7789Display(st, drawing)

    async def start(self):
        await asyncio.Event().wait()

