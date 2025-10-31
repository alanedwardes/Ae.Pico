MVLSB = 0
RGB565 = 1
GS4_HMSB = 2
MHLSB = 3
MHMSB = 4
GS2_HMSB = 5
GS8 = 6

class FrameBuffer:
    def __init__(self, buffer, width, height, mode, stride=None):
        if mode != RGB565:
            raise ValueError("Only RGB565 is supported in this CPython shim")
        self._buf = buffer
        self.width = int(width)
        self.height = int(height)
        self.mode = mode
        self.stride = int(stride) if stride is not None else int(width)

    def __buffer__(self, flags=None):
        return memoryview(self._buf)

    def _put_pixel(self, x, y, color):
        if x < 0 or y < 0 or x >= self.width or y >= self.height:
            return
        idx = (y * self.stride + x) * 2
        self._buf[idx] = color & 0xFF
        self._buf[idx + 1] = (color >> 8) & 0xFF

    def pixel(self, x, y, color=None):
        if color is None:
            idx = (y * self.stride + x) * 2
            return self._buf[idx] | (self._buf[idx + 1] << 8)
        self._put_pixel(x, y, color)

    def fill(self, color):
        lo = color & 0xFF
        hi = (color >> 8) & 0xFF
        row = bytearray([lo, hi] * self.stride)
        for y in range(self.height):
            start = y * self.stride * 2
            self._buf[start:start + self.stride * 2] = row

    def fill_rect(self, x, y, w, h, color):
        if w <= 0 or h <= 0:
            return
        x2 = x + w - 1
        y2 = y + h - 1
        x_start = max(0, x)
        x_end = min(self.width - 1, x2)
        if x_start > x_end:
            return
        lo = color & 0xFF
        hi = (color >> 8) & 0xFF
        row = bytearray([lo, hi] * (x_end - x_start + 1))
        for yy in range(max(0, y), min(self.height - 1, y2) + 1):
            start = (yy * self.stride + x_start) * 2
            self._buf[start:start + len(row)] = row

    def rect(self, x, y, w, h, color, fill=False):
        if w <= 0 or h <= 0:
            return
        x2 = x + w - 1
        y2 = y + h - 1
        if fill:
            self.fill_rect(x, y, w, h, color)
        else:
            self.fill_rect(x, y, w, 1, color)
            self.fill_rect(x, y + h - 1, w, 1, color)
            self.fill_rect(x, y, 1, h, color)
            self.fill_rect(x + w - 1, y, 1, h, color)

    def hline(self, x, y, w, color):
        self.fill_rect(x, y, w, 1, color)

    def vline(self, x, y, h, color):
        self.fill_rect(x, y, 1, h, color)

    def line(self, x0, y0, x1, y1, color):
        dx = abs(x1 - x0)
        dy = -abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx + dy
        while True:
            self._put_pixel(x0, y0, color)
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x0 += sx
            if e2 <= dx:
                err += dx
                y0 += sy

    def ellipse(self, x0, y0, rx, ry, color, fill=False, mask=0x0F):
        if rx <= 0 or ry <= 0:
            return
        x = 0
        y = ry
        rx2 = rx * rx
        ry2 = ry * ry
        tworx2 = 2 * rx2
        twory2 = 2 * ry2
        px = 0
        py = tworx2 * y

        # Region 1
        p = round(ry2 - (rx2 * ry) + (0.25 * rx2))
        while px < py:
            if fill:
                if mask & 0x01: self.hline(x0, y0 + y, x + 1, color)
                if mask & 0x02: self.hline(x0 - x, y0 + y, x + 1, color)
                if mask & 0x04: self.hline(x0 - x, y0 - y, x + 1, color)
                if mask & 0x08: self.hline(x0, y0 - y, x + 1, color)
            else:
                if mask & 0x01: self._put_pixel(x0 + x, y0 + y, color)
                if mask & 0x02: self._put_pixel(x0 - x, y0 + y, color)
                if mask & 0x04: self._put_pixel(x0 - x, y0 - y, color)
                if mask & 0x08: self._put_pixel(x0 + x, y0 - y, color)
            x += 1
            px += twory2
            if p < 0:
                p += ry2 + px
            else:
                y -= 1
                py -= tworx2
                p += ry2 + px - py

        # Region 2
        p = round(ry2 * (x + 0.5) * (x + 0.5) + rx2 * (y - 1) * (y - 1) - rx2 * ry2)
        while y >= 0:
            if fill:
                if mask & 0x01: self.hline(x0, y0 + y, x + 1, color)
                if mask & 0x02: self.hline(x0 - x, y0 + y, x + 1, color)
                if mask & 0x04: self.hline(x0 - x, y0 - y, x + 1, color)
                if mask & 0x08: self.hline(x0, y0 - y, x + 1, color)
            else:
                if mask & 0x01: self._put_pixel(x0 + x, y0 + y, color)
                if mask & 0x02: self._put_pixel(x0 - x, y0 + y, color)
                if mask & 0x04: self._put_pixel(x0 - x, y0 - y, color)
                if mask & 0x08: self._put_pixel(x0 + x, y0 - y, color)
            y -= 1
            py -= tworx2
            if p > 0:
                p += rx2 - py
            else:
                x += 1
                px += twory2
                p += rx2 - py + px

    def poly(self, x, y, points, color, fill=False):
        # points: array('h') with [x1,y1,x2,y2,...]
        pts = [(x + points[i], y + points[i + 1]) for i in range(0, len(points), 2)]
        if not fill:
            for i in range(len(pts)):
                x1, y1 = pts[i]
                x2, y2 = pts[(i + 1) % len(pts)]
                self.line(x1, y1, x2, y2, color)
            return

        # Scanline fill (even-odd rule)
        min_y = max(0, min(p[1] for p in pts))
        max_y = min(self.height - 1, max(p[1] for p in pts))
        for yy in range(min_y, max_y + 1):
            intersections = []
            for i in range(len(pts)):
                (x1, y1) = pts[i]
                (x2, y2) = pts[(i + 1) % len(pts)]
                if y1 == y2:
                    continue
                if yy < min(y1, y2) or yy >= max(y1, y2):
                    continue
                # Compute x intersection
                t = (yy - y1) / (y2 - y1)
                xi = x1 + t * (x2 - x1)
                intersections.append(int(xi))
            intersections.sort()
            for i in range(0, len(intersections), 2):
                x_start = intersections[i]
                if i + 1 >= len(intersections):
                    break
                x_end = intersections[i + 1]
                self.hline(x_start, yy, x_end - x_start + 1, color)

    def blit(self, source, x, y, key=-1, palette=None):
        # Minimal same-format blit; ignores palette for RGB565
        if isinstance(source, FrameBuffer):
            src = source
            src_mv = src.__buffer__()
            src_w, src_h = src.width, src.height
            src_stride = src.stride
        else:
            try:
                buf, src_w, src_h, fmt = source[0], int(source[1]), int(source[2]), int(source[3])
            except Exception:
                return
            if fmt != RGB565:
                return
            src_mv = memoryview(buf)
            src_stride = src_w
        if x >= self.width or y >= self.height or -x >= src_w or -y >= src_h:
            return
        x0 = max(0, x)
        y0 = max(0, y)
        sx0 = max(0, -x)
        sy0 = max(0, -y)
        x1 = min(self.width, x + src_w)
        y1 = min(self.height, y + src_h)
        for yy, sy in zip(range(y0, y1), range(sy0, sy0 + (y1 - y0))):
            dst_off = (yy * self.stride + x0) * 2
            src_off = (sy * src_stride + sx0) * 2
            count = (x1 - x0) * 2
            # No color key/palette support for RGB565 in this shim
            self._buf[dst_off:dst_off + count] = src_mv[src_off:src_off + count]

    def scroll(self, xstep, ystep):
        if xstep == 0 and ystep == 0:
            return
        # Create a copy to avoid stomping as we move
        src = self._buf[:]
        for y in range(self.height):
            for x in range(self.width):
                nx = x + xstep
                ny = y + ystep
                if 0 <= nx < self.width and 0 <= ny < self.height:
                    src_idx = (y * self.stride + x) * 2
                    dst_idx = (ny * self.stride + nx) * 2
                    self._buf[dst_idx:dst_idx + 2] = src[src_idx:src_idx + 2]

    def text(self, s, x, y, color=1):
        # No-op placeholder; text rendering is handled at higher level
        return

