import framebuf
import math

class Drawing(framebuf.FrameBuffer):
    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.mode = framebuf.RGB565
        self._buf = bytearray(width * height * 2)
        super().__init__(self._buf, width, height, self.mode)
        self.fill(0)
        self._driver = None
        # Pre-allocate a scratch buffer to reduce fragmentation during drawing operations
        self._scratch_buffer = bytearray(1024)

    def get_scratch_buffer(self, required_size=0):
        """Return a memoryview of the scratch buffer. 
        If required_size > allocated, it will allocate a new one (should be rare)."""
        if required_size > len(self._scratch_buffer):
            # Fallback for unusually large requests
            return bytearray(required_size)
        return memoryview(self._scratch_buffer)

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
        if self._driver is None:
            return

        if region is None:
            region = (0, 0, self.width, self.height)
        
        self._driver.render(self._buf, self.width, self.height, region)

    def _dim_color(self, color, factor):
        # Factor 0.0 to 1.0
        r = (color >> 11) & 0x1F
        g = (color >> 5) & 0x3F
        b = color & 0x1F
        
        r = int(r * factor)
        g = int(g * factor)
        b = int(b * factor)
        
        return (r << 11) | (g << 5) | b

    def aa_circle(self, cx, cy, radius, color):
        # Draw an anti-aliased circle
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
