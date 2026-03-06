import framebuf
import math

class Drawing:
    def __init__(self, width, height, color_mode='RGB565'):
        self.width = width
        self.height = height
        self.color_mode = color_mode
        self._driver = None

        if color_mode == 'RGB565':
            self.mode = framebuf.RGB565
            self.bytes_per_pixel = 2
        else:
            self.mode = framebuf.GS8
            self.bytes_per_pixel = 1

        self._framebuffer = bytearray(width * height * self.bytes_per_pixel)
        self.fb = framebuf.FrameBuffer(self._framebuffer, width, height, self.mode)
        self.fb.fill(0)
        
        # Pre-allocate a scratch buffer to reduce fragmentation during drawing operations
        self._scratch_buffer = bytearray(1024)

    def pack(self, color24):
        r = (color24 >> 16) & 0xFF
        g = (color24 >> 8) & 0xFF
        b = color24 & 0xFF
        if self.color_mode == 'RGB565':
            return ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
        else:
            return (r & 0xE0) | ((g & 0xE0) >> 3) | ((b & 0xC0) >> 6)

    # --- Framebuf Wrappers ---
    def pixel(self, x, y, color):
        self.fb.pixel(x, y, self.pack(color))

    def rect(self, x, y, w, h, color, fill=False):
        c = self.pack(color)
        if fill:
            self.fb.fill_rect(x, y, w, h, c)
        else:
            self.fb.rect(x, y, w, h, c)
            
    def fill_rect(self, x, y, w, h, color):
        self.fb.fill_rect(x, y, w, h, self.pack(color))

    def fill(self, color):
        self.fb.fill(self.pack(color))

    def text(self, s, x, y, color):
        self.fb.text(s, x, y, self.pack(color))
        
    def line(self, x1, y1, x2, y2, color):
        self.fb.line(x1, y1, x2, y2, self.pack(color))
        
    def hline(self, x, y, w, color):
        self.fb.hline(x, y, w, self.pack(color))

    def vline(self, x, y, h, color):
        self.fb.vline(x, y, h, self.pack(color))

    def ellipse(self, x, y, xr, yr, color, fill=False):
        c = self.pack(color)
        self.fb.ellipse(x, y, xr, yr, c, fill)
        
    def poly(self, x, y, coords, color, fill=False):
        c = self.pack(color)
        self.fb.poly(x, y, coords, c, fill)
        
    def scroll(self, xstep, ystep):
        self.fb.scroll(xstep, ystep)

    def blit(self, fbuf, x, y, key=-1, palette=None):
        self.fb.blit(fbuf, x, y, key, palette)
    # -------------------------

    def get_scratch_buffer(self, required_size=0):
        """Return a memoryview of the scratch buffer. 
        If required_size > allocated, it will allocate a new one (should be rare)."""
        if required_size > len(self._scratch_buffer):
            # Fallback for unusually large requests
            return bytearray(required_size)
        return memoryview(self._scratch_buffer)

    @property
    def framebuffer(self):
        return memoryview(self._framebuffer)

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
        
        self._driver.render(self._framebuffer, self.width, self.height, region)
