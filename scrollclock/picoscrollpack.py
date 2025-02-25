from picographics import PicoGraphics, DISPLAY_SCROLL_PACK, PEN_P8
from picoscroll import PicoScroll

class PicoScrollPack:
    def create(provider):
        provider['graphics'] = PicoGraphics(DISPLAY_SCROLL_PACK, pen_type=PEN_P8)
        provider['scroll'] = PicoScroll()
              
    async def start(self):
        raise NotImplementedError
