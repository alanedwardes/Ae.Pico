import sys
import math
import numpy as np

MVLSB = 0
RGB565 = 1
GS4_HMSB = 2
MHLSB = 3
MHMSB = 4
GS2_HMSB = 5
GS8 = 6

class FrameBuffer:
    def __init__(self, buffer, width, height, mode, stride=None):
        if mode != RGB565 and mode != GS8:
             # We mainly support RGB565 for the framebuffer itself in this shim, 
             # but GS8 might be used for sources.
             # Initializing a framebuffer in GS8 is possible if we want to simulate 8-bit buffers.
             pass

        self._buf = buffer
        self.width = int(width)
        self.height = int(height)
        self.mode = mode
        self.stride = int(stride) if stride is not None else int(width)
        
        # STRICT NUMPY INITIALIZATION
        dtype = np.uint16 if mode == RGB565 else np.uint8
        
        # Create numpy view
        self._np_buf = np.frombuffer(self._buf, dtype=dtype)
        
        # Validate and reshape
        expected_elems = self.stride * self.height
        if self._np_buf.size < expected_elems:
            raise ValueError(f"Buffer too small for framebuf: {self._np_buf.size} < {expected_elems}")
            
        # Truncate if larger (e.g. bytearray is generous)
        if self._np_buf.size > expected_elems:
             self._np_buf = self._np_buf[:expected_elems]
             
        self._np_buf = self._np_buf.reshape((self.height, self.stride))

    def __buffer__(self, flags=None):
        return memoryview(self._buf)

    def _put_pixel(self, x, y, color):
        if 0 <= x < self.width and 0 <= y < self.height:
            self._np_buf[y, x] = color

    def pixel(self, x, y, color=None):
        if color is None:
            if 0 <= x < self.width and 0 <= y < self.height:
                return int(self._np_buf[y, x])
            return 0
        self._put_pixel(x, y, color)

    def fill(self, color):
        self._np_buf.fill(color)

    def fill_rect(self, x, y, w, h, color):
        if w <= 0 or h <= 0:
            return
        
        x0 = max(0, x)
        y0 = max(0, y)
        x1 = min(self.width, x + w)
        y1 = min(self.height, y + h)
        
        if x1 > x0 and y1 > y0:
            self._np_buf[y0:y1, x0:x1] = color

    def rect(self, x, y, w, h, color, fill=False):
        if w <= 0 or h <= 0:
            return
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
        # We can vectorize lines, but Bresenham is tricky.
        # However, we can optimize by pre-calculating points or just using tight numpy access.
        # Since 'line' is not easily bulk-vectorizable without drawing libs (like cv2/PIL),
        # we keep the algorithm but ensure strict numpy access via _put_pixel or direct indexing.
        
        dx = x1 - x0
        sx = 1 if dx > 0 else -1
        dx = abs(dx)

        dy = y1 - y0
        sy = 1 if dy > 0 else -1
        dy = abs(dy)

        steep = False
        if dy > dx:
            x0, y0 = y0, x0
            x1, y1 = y1, x1
            dx, dy = dy, dx
            sx, sy = sy, sx
            steep = True

        e = 2 * dy - dx
        for _ in range(dx):
            if steep:
                if 0 <= x0 < self.height and 0 <= y0 < self.width:
                    self._np_buf[x0, y0] = color
            else:
                if 0 <= y0 < self.height and 0 <= x0 < self.width:
                    self._np_buf[y0, x0] = color
            while e >= 0:
                y0 += sy
                e -= 2 * dx
            x0 += sx
            e += 2 * dy
        
        if steep:
             if 0 <= x1 < self.height and 0 <= y1 < self.width:
                self._np_buf[x1, y1] = color
        else:
             if 0 <= y1 < self.height and 0 <= x1 < self.width:
                self._np_buf[y1, x1] = color

    def ellipse(self, x0, y0, rx, ry, color, fill=False, mask=0x0F):
        if rx < 0 or ry < 0: return
        if rx == 0 and ry == 0:
            if mask & 0x0F: self._put_pixel(x0, y0, color)
            return

        def draw_points(cx, cy, x, y):
            if fill:
                if mask & 0x01: self.hline(cx, cy - y, x + 1, color)
                if mask & 0x02: self.hline(cx - x, cy - y, x + 1, color)
                if mask & 0x04: self.hline(cx - x, cy + y, x + 1, color)
                if mask & 0x08: self.hline(cx, cy + y, x + 1, color)
            else:
                if mask & 0x01: self._put_pixel(cx + x, cy - y, color)
                if mask & 0x02: self._put_pixel(cx - x, cy - y, color)
                if mask & 0x04: self._put_pixel(cx - x, cy + y, color)
                if mask & 0x08: self._put_pixel(cx + x, cy + y, color)
        
        # Standard Midpoint Ellipse Logic
        two_asquare = 2 * rx * rx
        two_bsquare = 2 * ry * ry
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
        pts = [(x + points[i], y + points[i + 1]) for i in range(0, len(points), 2)]
        n = len(pts)
        if n == 0: return
        if not fill:
            for i in range(n):
                self.line(pts[i][0], pts[i][1], pts[(i+1)%n][0], pts[(i+1)%n][1], color)
            return

        min_y = max(0, min(py for _, py in pts))
        max_y = min(self.height - 1, max(py for _, py in pts))
        
        for row in range(min_y, max_y + 1):
            nodes = []
            px1, py1 = pts[0]
            idx = n - 1
            while idx >= 0:
                px2, py2 = pts[idx]
                if py1 != py2 and ((py1 > row and py2 <= row) or (py1 <= row and py2 > row)):
                    temp = (32 * (px2 - px1) * (row - py1)) // (py2 - py1)
                    node = (32 * px1 + temp + 16) // 32
                    nodes.append(node)
                elif row == max(py1, py2):
                    if py1 < py2: self._put_pixel(px2, py2, color)
                    elif py2 < py1: self._put_pixel(px1, py1, color)
                    else: self.line(px1, py1, px2, py2, color)
                px1, py1 = px2, py2
                idx -= 1
            if not nodes: continue
            nodes.sort()
            for j in range(0, len(nodes) - 1, 2):
                x_start = nodes[j]
                x_end = nodes[j + 1]
                self.fill_rect(x_start, row, (x_end - x_start) + 1, 1, color)

    def blit(self, source, x, y, key=-1, palette=None):
        # Resolve source to numpy array
        src_np = None
        src_fmt = None
        src_w, src_h = 0, 0
        
        if isinstance(source, FrameBuffer):
             src_np = source._np_buf
             src_w, src_h = source.width, source.height
             src_fmt = source.mode
        else:
            # Handle tuple/list source
            try:
                if len(source) >= 5:
                    buf, src_w, src_h, src_fmt, stride = source[0], int(source[1]), int(source[2]), int(source[3]), int(source[4])
                else:
                    buf, src_w, src_h, src_fmt = source[0], int(source[1]), int(source[2]), int(source[3])
                    stride = src_w
                
                # Convert buffer to numpy
                dtype = np.uint16 if src_fmt == RGB565 else np.uint8
                src_np = np.frombuffer(buf, dtype=dtype)
                
                # Careful with incomplete buffers or strides
                req_size = stride * src_h
                if src_np.size > req_size:
                    src_np = src_np[:req_size]
                src_np = src_np.reshape((src_h, stride))
                
            except Exception as e:
                # If we can't make sense of source, do nothing
                return

        # Intersection logic
        # Destination clips
        x0 = max(0, x)
        y0 = max(0, y)
        x1 = min(self.width, x + src_w)
        y1 = min(self.height, y + src_h)
        
        if x0 >= x1 or y0 >= y1:
            return

        # Source offsets
        sx0 = x0 - x
        sy0 = y0 - y
        sx1 = sx0 + (x1 - x0)
        sy1 = sy0 + (y1 - y0)
        
        # Extract source region
        try:
            src_region = src_np[sy0:sy1, sx0:sx1]
        except IndexError:
            return

        # Resolve Palette if present
        if palette is not None:
             # Convert palette to numpy lookup table
             pal_np = None
             if isinstance(palette, FrameBuffer):
                 pal_np = palette._np_buf.flatten()
             else:
                 # Try to parse list/tuple palette
                 try:
                      pbuf = palette[0]
                      # Palette is usually RGB565
                      pal_np = np.frombuffer(pbuf, dtype=np.uint16)
                 except:
                      pass
             
             if pal_np is not None:
                  # Vectorized lookup: src_region (indices) -> RGB565
                  # src_region must be integer type suitable for indexing
                  try:
                      src_region = pal_np[src_region]
                      src_fmt = RGB565 # Now it is RGB565
                  except IndexError:
                      return # Indices out of bounds of palette

        # Format Conversion
        if src_fmt == GS8 and self.mode == RGB565:
             # Vectorized Convert GS8 -> RGB565
             # r = (g >> 3) << 11
             # g = (g >> 2) << 5
             # b = g >> 3
             # Avoiding overflow by casting to uint16 first
             g = src_region.astype(np.uint16)
             r = (g >> 3) << 11
             g6 = (g >> 2) << 5
             b = (g >> 3)
             src_region = r | g6 | b
             
        # Transparency (Key)
        mask = None
        if key != -1:
             mask = (src_region != key)
        
        # Blit
        # If mask exists, use it
        dst_region_slice = (slice(y0, y1), slice(x0, x1))
        
        if mask is not None:
             # Masked assignment: dst[mask] = src[mask]
             # But we need to act on the slice of dst
             # numpy doesn't support dst[slice][mask] = src[mask] well if shapes differ, 
             # but here shapes align.
             # Better: dst_view = dst[slice]; dst_view[mask] = src_region[mask]
             
             dst_view = self._np_buf[y0:y1, x0:x1]
             # Ensure shapes match exactly (they should)
             if dst_view.shape == src_region.shape:
                  dst_view[mask] = src_region[mask]
        else:
             self._np_buf[y0:y1, x0:x1] = src_region

    def scroll(self, xstep, ystep):
        if xstep == 0 and ystep == 0:
            return
            
        temp = self._np_buf.copy()
        
        sx = max(0, -xstep)
        sy = max(0, -ystep)
        dx = max(0, xstep)
        dy = max(0, ystep)
        
        w = self.width - abs(xstep)
        h = self.height - abs(ystep)
        
        if w > 0 and h > 0:
            self._np_buf[dy:dy+h, dx:dx+w] = temp[sy:sy+h, sx:sx+w]

    def text(self, s, x, y, color=1):
        pass
