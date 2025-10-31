import framebuf

class Drawing(framebuf.FrameBuffer):
    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.mode = framebuf.RGB565
        self._buf = bytearray(width * height * 2)
        super().__init__(self._buf, width, height, self.mode)
        self.pen = 0
        self.thickness = 1
        self.font = 'bitmap8'
        self._clip = None  # (x, y, w, h)
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

    def set_thickness(self, thickness):
        self.thickness = thickness

    def get_bounds(self):
        return (self.width, self.height)

    def set_clip(self, x, y, w, h):
        self._clip = (max(0, x), max(0, y), max(0, w), max(0, h))

    def remove_clip(self):
        self._clip = None

    def _apply_clip_rect(self, x, y, w, h):
        if self._clip is None:
            return x, y, w, h
        cx, cy, cw, ch = self._clip
        x2 = x + w
        y2 = y + h
        nx1 = max(x, cx)
        ny1 = max(y, cy)
        nx2 = min(x2, cx + cw)
        ny2 = min(y2, cy + ch)
        nw = max(0, nx2 - nx1)
        nh = max(0, ny2 - ny1)
        return nx1, ny1, nw, nh

    def clear(self):
        self.rect(0, 0, self.width, self.height, self.pen, True)

    def pixel(self, x, y):
        if self._clip is not None:
            cx, cy, cw, ch = self._clip
            if not (cx <= x < cx + cw and cy <= y < cy + ch):
                return
        super().pixel(x, y, self.pen)

    def line(self, x1, y1, x2, y2, thickness=1):
        # Thickness is approximated by drawing parallel lines
        if thickness <= 1:
            super().line(x1, y1, x2, y2, self.pen)
            return
        # Simple orthogonal thickness approximation
        if x1 == x2:
            super().rect(x1 - thickness // 2, min(y1, y2), thickness, abs(y2 - y1) + 1, self.pen, True)
        elif y1 == y2:
            super().rect(min(x1, x2), y1 - thickness // 2, abs(x2 - x1) + 1, thickness, self.pen, True)
        else:
            super().line(x1, y1, x2, y2, self.pen)

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
        self._driver.render(self.__buffer__(), self.width, self.height)


