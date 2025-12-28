from picographics import PicoGraphics, DISPLAY_PICO_DISPLAY_2
from pimoroni import RGBLED

# Provides a service registration for 'display'
# Which is a PicoGraphics instance for the current display
class PicoGraphicsLimitedPalette(PicoGraphics):
    async def activate(self, max_palette_size):
        self.max_palette_size = max_palette_size
        self.palette = []
        self.lookup_cache = {}

    def color_distance(self, c1, c2):
        return ((c1[0] - c2[0]) ** 2 +
                (c1[1] - c2[1]) ** 2 +
                (c1[2] - c2[2]) ** 2)

    def create_pen(self, r, g, b):
        color = (r, g, b)
        if color in self.palette:
            return self.palette.index(color)

        pen_index = len(self.palette)
        if pen_index >= self.max_palette_size:
            # Use cache for overflow lookups
            if color in self.lookup_cache:
                return self.lookup_cache[color]

            # First, try to find the nearest grey in the palette, but skip black (0,0,0)
            def is_grey(c):
                return c[0] == c[1] == c[2] and c != (0, 0, 0)

            grey_indices = [i for i, c in enumerate(self.palette) if is_grey(c)]
            if grey_indices:
                # Compute the luminance of the requested color
                luminance = int(0.299 * r + 0.587 * g + 0.114 * b)
                closest_grey_index = min(
                    grey_indices,
                    key=lambda i: abs(self.palette[i][0] - luminance)
                )
                self.lookup_cache[color] = closest_grey_index
                return closest_grey_index

            # Fallback to nearest RGB color
            closest_index = min(
                range(len(self.palette)),
                key=lambda i: self.color_distance(self.palette[i], color)
            )
            self.lookup_cache[color] = closest_index
            return closest_index

        self.palette.insert(pen_index, color)
        self.update_pen(pen_index, r, g, b)
        return pen_index

class PicoDisplay2:
    def create(provider):
        config = provider['config'].get('display', {})
        
        led_pins = config.get('led')
        if led_pins is not None:
            RGBLED(*led_pins).set_rgb(0, 0, 0)
        
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
