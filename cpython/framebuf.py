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
        dx = x1 - x0
        sx = 1 if dx > 0 else -1
        dx = abs(dx)

        dy = y1 - y0
        sy = 1 if dy > 0 else -1
        dy = abs(dy)

        steep = False
        if dy > dx:
            # swap axes
            x0, y0 = y0, x0
            x1, y1 = y1, x1
            dx, dy = dy, dx
            sx, sy = sy, sx
            steep = True

        e = 2 * dy - dx
        for _ in range(dx):
            if steep:
                self._put_pixel(y0, x0, color)
            else:
                self._put_pixel(x0, y0, color)
            while e >= 0:
                y0 += sy
                e -= 2 * dx
            x0 += sx
            e += 2 * dy
        # final endpoint
        if steep:
            self._put_pixel(y1, x1, color)
        else:
            self._put_pixel(x1, y1, color)

    def ellipse(self, x0, y0, rx, ry, color, fill=False, mask=0x0F):
        if rx < 0 or ry < 0:
            return
        if rx == 0 and ry == 0:
            if mask & 0x0F:
                self._put_pixel(x0, y0, color)
            return

        def draw_points(cx, cy, x, y):
            if fill:
                # Q1 (top-right)
                if mask & 0x01:
                    self.hline(cx, cy - y, x + 1, color)
                # Q2 (top-left)
                if mask & 0x02:
                    self.hline(cx - x, cy - y, x + 1, color)
                # Q3 (bottom-left)
                if mask & 0x04:
                    self.hline(cx - x, cy + y, x + 1, color)
                # Q4 (bottom-right)
                if mask & 0x08:
                    self.hline(cx, cy + y, x + 1, color)
            else:
                if mask & 0x01:
                    self._put_pixel(cx + x, cy - y, color)
                if mask & 0x02:
                    self._put_pixel(cx - x, cy - y, color)
                if mask & 0x04:
                    self._put_pixel(cx - x, cy + y, color)
                if mask & 0x08:
                    self._put_pixel(cx + x, cy + y, color)

        two_asquare = 2 * rx * rx
        two_bsquare = 2 * ry * ry

        # Region 1
        x = rx
        y = 0
        xchange = ry * ry * (1 - 2 * rx)
        ychange = rx * rx
        ellipse_error = 0
        stoppingx = two_bsquare * rx
        stoppingy = 0
        while stoppingx >= stoppingy:
            draw_points(x0, y0, x, y)
            y += 1
            stoppingy += two_asquare
            ellipse_error += ychange
            ychange += two_asquare
            if (2 * ellipse_error + xchange) > 0:
                x -= 1
                stoppingx -= two_bsquare
                ellipse_error += xchange
                xchange += two_bsquare

        # Region 2
        x = 0
        y = ry
        xchange = ry * ry
        ychange = rx * rx * (1 - 2 * ry)
        ellipse_error = 0
        stoppingx = 0
        stoppingy = two_asquare * ry
        while stoppingx <= stoppingy:
            draw_points(x0, y0, x, y)
            x += 1
            stoppingx += two_bsquare
            ellipse_error += xchange
            xchange += two_bsquare
            if (2 * ellipse_error + ychange) > 0:
                y -= 1
                stoppingy -= two_asquare
                ellipse_error += ychange
                ychange += two_asquare

    def poly(self, x, y, points, color, fill=False):
        # points: array('h') with [x1,y1,x2,y2,...]
        # Build absolute coordinate list for simplicity
        pts = [(x + points[i], y + points[i + 1]) for i in range(0, len(points), 2)]
        n = len(pts)
        if n == 0:
            return
        if not fill:
            for i in range(n):
                x1, y1 = pts[i]
                x2, y2 = pts[(i + 1) % n]
                self.line(x1, y1, x2, y2, color)
            return

        # Integer scanline fill with fixed-point rounding and vertex fixes
        min_y = max(0, min(py for _, py in pts))
        max_y = min(self.height - 1, max(py for _, py in pts))
        for row in range(min_y, max_y + 1):
            nodes = []
            px1, py1 = pts[0]
            i = n * 2 - 1  # mirror C loop order (not strictly required)
            idx = n - 1
            while idx >= 0:
                px2, py2 = pts[idx]
                # Crossing test excluding bottom pixels
                if py1 != py2 and ((py1 > row and py2 <= row) or (py1 <= row and py2 > row)):
                    # Fixed-point rounding to nearest as per C implementation
                    temp = (32 * (px2 - px1) * (row - py1)) // (py2 - py1)
                    node = (32 * px1 + temp + 16) // 32
                    nodes.append(node)
                elif row == max(py1, py2):
                    # Patch local minima/horizontal edges
                    if py1 < py2:
                        self._put_pixel(px2, py2, color)
                    elif py2 < py1:
                        self._put_pixel(px1, py1, color)
                    else:
                        self.line(px1, py1, px2, py2, color)
                px1, py1 = px2, py2
                idx -= 1

            if not nodes:
                continue

            nodes.sort()
            for j in range(0, len(nodes) - 1, 2):
                x_start = nodes[j]
                x_end = nodes[j + 1]
                self.fill_rect(x_start, row, (x_end - x_start) + 1, 1, color)

    def blit(self, source, x, y, key=-1, palette=None):
        # Resolve source buffer/format
        if isinstance(source, FrameBuffer):
            src_mv = source.__buffer__()
            src_w, src_h = source.width, source.height
            src_stride = source.stride
            src_fmt = source.mode
        else:
            try:
                if len(source) >= 5:
                    buf, src_w, src_h, src_fmt, src_stride = (
                        source[0], int(source[1]), int(source[2]), int(source[3]), int(source[4])
                    )
                else:
                    buf, src_w, src_h, src_fmt = (
                        source[0], int(source[1]), int(source[2]), int(source[3])
                    )
                    src_stride = src_w
            except Exception:
                return
            try:
                src_mv = memoryview(buf)
            except Exception:
                return

        # Prepare optional palette (RGB565 expected)
        pal_mv = None
        pal_stride = 0
        pal_fmt = None
        if palette is not None:
            if isinstance(palette, FrameBuffer):
                pal_mv = palette.__buffer__()
                pal_stride = palette.stride
                pal_fmt = palette.mode
            else:
                try:
                    if len(palette) >= 5:
                        pbuf, pw, ph, pal_fmt, pal_stride = (
                            palette[0], int(palette[1]), int(palette[2]), int(palette[3]), int(palette[4])
                        )
                    else:
                        pbuf, pw, ph, pal_fmt = (
                            palette[0], int(palette[1]), int(palette[2]), int(palette[3])
                        )
                        pal_stride = pw
                    pal_mv = memoryview(pbuf)
                except Exception:
                    pal_mv = None
            # Only accept RGB565 palettes in this shim
            if pal_fmt != RGB565:
                pal_mv = None

        # Trivial reject if completely out of bounds
        if x >= self.width or y >= self.height or -x >= src_w or -y >= src_h:
            return

        # Clip to destination and compute starting source coords
        x0 = max(0, x)
        y0 = max(0, y)
        sx0 = max(0, -x)
        sy0 = max(0, -y)
        x1 = min(self.width, x + src_w)
        y1 = min(self.height, y + src_h)

        # Fast path: direct row copy for RGB565 without key/palette
        if src_fmt == RGB565 and pal_mv is None and key == -1:
            for yy, sy in zip(range(y0, y1), range(sy0, sy0 + (y1 - y0))):
                dst_off = (yy * self.stride + x0) * 2
                src_off = (sy * src_stride + sx0) * 2
                count = (x1 - x0) * 2
                self._buf[dst_off:dst_off + count] = src_mv[src_off:src_off + count]
            return

        # Helper to read a source pixel and map via palette if needed
        def read_src_color(sx, sy):
            if src_fmt == RGB565:
                o = (sy * src_stride + sx) * 2
                return src_mv[o] | (src_mv[o + 1] << 8)
            elif src_fmt == GS8:
                o = (sy * src_stride + sx)
                idx = src_mv[o]
                if pal_mv is not None:
                    po = (0 * pal_stride + int(idx)) * 2
                    return pal_mv[po] | (pal_mv[po + 1] << 8)
                # Fallback: approximate grayscale mapping to RGB565
                g = int(idx) & 0xFF
                r = g >> 3
                g6 = g >> 2
                b = g >> 3
                return (r << 11) | (g6 << 5) | b
            else:
                # Unsupported source format in this shim
                return None

        # Per-pixel loop to support key/palette
        width = x1 - x0
        for dy, sy in zip(range(y0, y1), range(sy0, sy0 + (y1 - y0))):
            sx = sx0
            dx = x0
            for _ in range(width):
                col = read_src_color(sx, sy)
                if col is not None and (key == -1 or col != key):
                    off = (dy * self.stride + dx) * 2
                    self._buf[off] = col & 0xFF
                    self._buf[off + 1] = (col >> 8) & 0xFF
                sx += 1
                dx += 1

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

