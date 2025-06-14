from picographics import PicoGraphics, DISPLAY_PICO_DISPLAY_2

# Provides a service registration for 'display'
# Which is a PicoGraphics instance for the current display
class PicoGraphicsLimitedPalette(PicoGraphics):
    def activate(self, max_palette_size):
        self.max_palette_size = max_palette_size
        self.palette = []
        self.original_update = self.update
        self.update = self.patched_update
    
    def create_pen(self, r, g, b):
        color = (r, g, b)
        if color in self.palette:
            return self.palette.index(color)
        
        pen_index = len(self.palette)
        if pen_index >= self.max_palette_size:
            print(f'Warning: no palette space left for {color}')
            return len(self.palette) - 1
        
        self.palette.insert(pen_index, color)
        self.update_pen(pen_index, r, g, b)
        return pen_index
    
    def patched_update(self):
        self.original_update()
        self.palette = []

class PicoDisplay2:
    def create(provider):
        config = provider['config'].get('display', {})
        mode = config.get('mode', 'RGB332')
        
        pen_type = None
        limited_palette = None
        if mode == 'P4':
            from picographics import PEN_P4
            pen_type = PEN_P4
            limited_palette = 16
        elif mode == 'P8':
            from picographics import PEN_P8
            pen_type = PEN_P8
            limited_palette = 256
        elif mode == 'RGB332':
            from picographics import PEN_RGB332
            pen_type = PEN_RGB332
        elif mode == 'RGB565':
            from picographics import PEN_RGB565
            pen_type = PEN_RGB565
        elif mode == 'RGB888':
            from picographics import PEN_RGB888
            pen_type = PEN_RGB888
        else:
            raise NotImplemented(f'Mode {mode} not implemented')
        
        init_params = dict(display=DISPLAY_PICO_DISPLAY_2, pen_type=pen_type, rotate=180 if config.get('rotate', False) else 0)
        
        if limited_palette is None:
            provider['display'] = PicoGraphics(**init_params)
        else:        
            graphics = PicoGraphicsLimitedPalette(**init_params)
            graphics.activate(limited_palette)
            provider['display'] = graphics
              
    async def start(self):
        raise NotImplementedError
