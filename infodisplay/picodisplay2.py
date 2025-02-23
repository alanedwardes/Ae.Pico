from picographics import PicoGraphics, DISPLAY_PICO_DISPLAY_2, PEN_P4

# Provides a service registration for 'display'
# Which is a PicoGraphics instance for the current display
class PicoDisplay2:
    def create(provider):
        config = provider['config'].get('display', {})
        provider['display'] = PicoGraphics(display=DISPLAY_PICO_DISPLAY_2, pen_type=PEN_P4, rotate=180 if config.get('rotate', False) else 0)
              
    async def start(self):
        raise NotImplementedError
