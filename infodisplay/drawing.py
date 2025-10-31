import framebuf

class Drawing(framebuf.FrameBuffer):
    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.mode = framebuf.RGB565
        self._buf = bytearray(width * height * 2)
        super().__init__(self._buf, width, height, self.mode)
        self.pen = 0
        self._driver = None

    @staticmethod
    def rgb(r, g, b):
        return ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)

    def set_driver(self, driver):
        self._driver = driver

    def create_pen(self, r, g, b):
        return Drawing.rgb(r, g, b)

    def set_pen(self, pen):
        self.pen = pen

    def get_bounds(self):
        return (self.width, self.height)

    def polygon(self, points):
        # points: list of (x, y)
        if not points:
            return
        from array import array
        flat = []
        for px, py in points:
            flat.append(px)
            flat.append(py)
        super().poly(0, 0, array('h', flat), self.pen, True)

    def update(self):
        if self._driver is None:
            return
        self._driver.render(self._buf, self.width, self.height)


