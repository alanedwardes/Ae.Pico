import math

class Drawing:
    def __init__(self, width, height):
        self.width = width
        self.height = height
        self._driver = None

    @staticmethod
    def rgb(r, g, b):
        return ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)

    def set_driver(self, driver):
        self._driver = driver

    def get_bounds(self):
        return (self.width, self.height)

    def set_backlight(self, brightness):
        if self._driver is None:
            return
        self._driver.set_backlight(brightness)

    def update(self, region=None):
        # No-op in direct rendering mode as changes are immediate
        pass

    def _dim_color(self, color, factor):
        # Factor 0.0 to 1.0
        r = (color >> 11) & 0x1F
        g = (color >> 5) & 0x3F
        b = color & 0x1F
        
        r = int(r * factor)
        g = int(g * factor)
        b = int(b * factor)
        
        return (r << 11) | (g << 5) | b

    def pixel(self, x, y, color):
        if self._driver:
            self._driver.pixel(x, y, color)

    def line(self, x1, y1, x2, y2, color):
        if self._driver:
            self._driver.line(x1, y1, x2, y2, color)

    def hline(self, x, y, w, color):
        if self._driver:
            self._driver.hline(x, y, w, color)

    def vline(self, x, y, h, color):
        if self._driver:
            self._driver.vline(x, y, h, color)

    def ellipse(self, x, y, xr, yr, color, fill=False, m=15):
        if self._driver:
            self._driver.ellipse(x, y, xr, yr, color, fill, m)

    def poly(self, x, y, coords, color, fill=False):
        if self._driver:
            self._driver.poly(x, y, coords, color, fill)

    def rect(self, x, y, w, h, color, fill=False):
        if self._driver:
            self._driver.rect(x, y, w, h, color, fill)

    def fill_rect(self, x, y, w, h, color):
        if self._driver:
            # fill_rect is usually same as rect with fill=True, but framebuf has it separate?
            # framebuf has fill_rect(x, y, w, h, c)
            self._driver.fill_rect(x, y, w, h, color)

    def fill(self, color):
        if self._driver:
            self._driver.fill(color)    

    def blit(self, source, x, y, key=0, palette=None):
        if self._driver:
            self._driver.blit(source, x, y, key, palette)

    async def load_stream(self, reader, x, y, w, h):
        if self._driver:
            await self._driver.load_stream(reader, x, y, w, h)
            
    def aa_circle(self, cx, cy, radius, color):
        # Draw an anti-aliased circle
        # This will be slow with direct pixel calls but functional
        r_int = int(radius) + 1
        for dy in range(-r_int, r_int + 1):
             for dx in range(-r_int, r_int + 1):
                dist = math.sqrt(dx*dx + dy*dy)
                
                if dist < radius - 1:
                    # Inner solid core
                    if 0 <= cy + dy < self.height and 0 <= cx + dx < self.width:
                        self.pixel(cx + dx, cy + dy, color)
                elif dist <= radius:
                    # Antialias edge
                    factor = 1.0 - (dist - (radius - 1))
                    if factor > 0:
                        c = self._dim_color(color, factor)
                        if 0 <= cy + dy < self.height and 0 <= cx + dx < self.width:
                            self.pixel(cx + dx, cy + dy, c)

    def text(self, s, x, y, color=0xFFFF):
        if self._driver:
            self._driver.text(s, x, y, color)
