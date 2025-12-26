import framebuf

class Drawing(framebuf.FrameBuffer):
    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.mode = framebuf.RGB565
        self._buf = bytearray(width * height * 2)
        super().__init__(self._buf, width, height, self.mode)
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
        if self._driver is None:
            return

        if region is None:
            region = (0, 0, self.width, self.height)
        
        self._driver.render(self._buf, self.width, self.height, region)

