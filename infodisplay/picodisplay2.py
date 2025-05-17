from picographics import PicoGraphics, DISPLAY_PICO_DISPLAY_2, PEN_P4

class ExtendedPicoGraphics(PicoGraphics):
    def set_pen_color(self, color, palette):
        if color in palette:
            pen_index = palette.index(color)
        else:
            palette.append(color)
            pen_index = len(palette) - 1
            self.update_pen(pen_index, color[0], color[1], color[2])
            
        self.set_pen(pen_index)

# Provides a service registration for 'display'
# Which is a PicoGraphics instance for the current display
class PicoDisplay2:    
    def create(provider):
        config = provider['config'].get('display', {})
        provider['display'] = ExtendedPicoGraphics(display=DISPLAY_PICO_DISPLAY_2, pen_type=PEN_P4, rotate=180 if config.get('rotate', False) else 0)
              
    async def start(self):
        raise NotImplementedError
