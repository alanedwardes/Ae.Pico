import sys
import struct

try:
    import micropython
    IS_MICROPYTHON = sys.implementation.name == 'micropython'
except ImportError:
    IS_MICROPYTHON = False

if not IS_MICROPYTHON:
    class micropython:
        @staticmethod
        def viper(f): return f
        @staticmethod
        def native(f): return f
        @staticmethod
        def const(x): return x
        @staticmethod
        def heap_lock(): pass
        @staticmethod
        def heap_unlock(): pass
    
    ptr8 = ptr16 = ptr32 = object

    def _as_ptr16(obj):
        """Helper to get a 16-bit word-indexed view in CPython."""
        if obj is None: return None
        if hasattr(obj, '_framebuffer'): return memoryview(obj._framebuffer).cast('H')
        if hasattr(obj, '_buf'): return memoryview(obj._buf).cast('H')
        return memoryview(obj).cast('H')

    def _as_ptr8(obj):
        """Helper to get 8-bit byte-indexed view in CPython."""
        if obj is None: return None
        if hasattr(obj, '_framebuffer'): return memoryview(obj._framebuffer).cast('B')
        if hasattr(obj, '_buf'): return memoryview(obj._buf).cast('B')
        return memoryview(obj).cast('B')
else:
    def _as_ptr16(obj):
        if hasattr(obj, '_framebuffer'): return obj._framebuffer
        if hasattr(obj, '_buf'): return obj._buf
        return obj
    def _as_ptr8(obj):
        if hasattr(obj, '_framebuffer'): return obj._framebuffer
        if hasattr(obj, '_buf'): return obj._buf
        return obj

@micropython.viper
def _blit_rect_gs8_to_rgb565_viper(dest: ptr16, d_off: int, d_stride: int,
                                 src: ptr8, s_off: int, s_stride: int,
                                 w: int, h: int, palette: ptr16, key: int):
    if key == -1:
        for y in range(h):
            d_p = d_off + y * d_stride
            s_p = s_off + y * s_stride
            for x in range(w):
                dest[d_p + x] = palette[src[s_p + x]]
    else:
        for y in range(h):
            d_p = d_off + y * d_stride
            s_p = s_off + y * s_stride
            for x in range(w):
                val = int(src[s_p + x])
                if val != key:
                    dest[d_p + x] = palette[val]

@micropython.viper
def _blit_rect_gs8_to_rgb565_direct_viper(dest: ptr16, d_off: int, d_stride: int,
                                 src: ptr8, s_off: int, s_stride: int,
                                 w: int, h: int, key: int):
    if key == -1:
        for y in range(h):
            d_p = d_off + y * d_stride
            s_p = s_off + y * s_stride
            for x in range(w):
                val = int(src[s_p + x])
                dest[d_p + x] = ((val & 0xF8) << 8) | ((val & 0xFC) << 3) | (val >> 3)
    else:
        for y in range(h):
            d_p = d_off + y * d_stride
            s_p = s_off + y * s_stride
            for x in range(w):
                val = int(src[s_p + x])
                if val != key:
                    dest[d_p + x] = ((val & 0xF8) << 8) | ((val & 0xFC) << 3) | (val >> 3)

@micropython.viper
def _blit_rect_rgb565_to_rgb565_viper(dest: ptr16, d_off: int, d_stride: int,
                                 src: ptr16, s_off: int, s_stride: int,
                                 w: int, h: int, key: int):
    if key == -1:
        for y in range(h):
            d_p = d_off + y * d_stride
            s_p = s_off + y * s_stride
            for x in range(w):
                dest[d_p + x] = src[s_p + x]
    else:
        for y in range(h):
            d_p = d_off + y * d_stride
            s_p = s_off + y * s_stride
            for x in range(w):
                val = int(src[s_p + x])
                if val != key:
                    dest[d_p + x] = val

@micropython.viper
def _blit_rect_8bit_to_8bit_viper(dest: ptr8, d_off: int, d_stride: int,
                                 src: ptr8, s_off: int, s_stride: int,
                                 w: int, h: int, key: int):
    if key == -1:
        for y in range(h):
            d_p = d_off + y * d_stride
            s_p = s_off + y * s_stride
            for x in range(w):
                dest[d_p + x] = src[s_p + x]
    else:
        for y in range(h):
            d_p = d_off + y * d_stride
            s_p = s_off + y * s_stride
            for x in range(w):
                val = int(src[s_p + x])
                if val != key:
                    dest[d_p + x] = val

@micropython.viper
def _blit_rect_gs8_to_8bit_palette_viper(dest: ptr8, d_off: int, d_stride: int,
                                 src: ptr8, s_off: int, s_stride: int,
                                 w: int, h: int, palette: ptr8, key: int):
    if key == -1:
        for y in range(h):
            d_p = d_off + y * d_stride
            s_p = s_off + y * s_stride
            for x in range(w):
                dest[d_p + x] = palette[src[s_p + x]]
    else:
        for y in range(h):
            d_p = d_off + y * d_stride
            s_p = s_off + y * s_stride
            for x in range(w):
                val = int(src[s_p + x])
                if val != key:
                    dest[d_p + x] = palette[val]

@micropython.viper
def _fill_rows_rgb565_viper(dest: ptr16, d_off: int, d_stride: int, w: int, h: int, bg: int):
    for y in range(h):
        d_p = d_off + y * d_stride
        for x in range(w):
            dest[d_p + x] = bg

@micropython.viper
def _fill_rows_8bit_viper(dest: ptr8, d_off: int, d_stride: int, w: int, h: int, bg: int):
    for y in range(h):
        d_p = d_off + y * d_stride
        for x in range(w):
            dest[d_p + x] = bg

@micropython.viper
def _composite_glyph_row_gs8_to_rgb565_viper(dest: ptr16, d_off: int, d_stride: int,
                                 src: ptr8, s_off: int, s_stride: int,
                                 left_w: int, glyph_w: int, right_w: int, h: int,
                                 palette: ptr16, bg: int):
    for y in range(h):
        d_p = d_off + y * d_stride
        s_p = s_off + y * s_stride
        for x in range(left_w):
            dest[d_p + x] = bg
        gp = d_p + left_w
        for x in range(glyph_w):
            v = int(src[s_p + x])
            dest[gp + x] = bg if v == 0 else palette[v]
        rp = gp + glyph_w
        for x in range(right_w):
            dest[rp + x] = bg

@micropython.viper
def _composite_glyph_row_gs8_to_8bit_viper(dest: ptr8, d_off: int, d_stride: int,
                                 src: ptr8, s_off: int, s_stride: int,
                                 left_w: int, glyph_w: int, right_w: int, h: int,
                                 palette: ptr8, bg: int):
    for y in range(h):
        d_p = d_off + y * d_stride
        s_p = s_off + y * s_stride
        for x in range(left_w):
            dest[d_p + x] = bg
        gp = d_p + left_w
        for x in range(glyph_w):
            v = int(src[s_p + x])
            dest[gp + x] = bg if v == 0 else palette[v]
        rp = gp + glyph_w
        for x in range(right_w):
            dest[rp + x] = bg

_scratch_buf = None
_scratch_view = None

def fill_region(framebuffer, fb_width, fb_height, x, y, w, h, bg_pixel, clip=None):
    if w <= 0 or h <= 0: return

    min_x, min_y = 0, 0
    max_x, max_y = fb_width, fb_height
    if clip:
        ccx, ccy, ccw, cch = clip
        min_x, min_y = max(min_x, ccx), max(min_y, ccy)
        max_x, max_y = min(max_x, ccx + ccw), min(max_y, ccy + cch)

    if x >= max_x or y >= max_y: return
    if x + w <= min_x or y + h <= min_y: return

    start_row = max(0, min_y - y)
    end_row = min(h, max_y - y)
    left_clip = max(0, min_x - x)
    right_clip = max(0, x + w - max_x)
    draw_w = w - left_clip - right_clip
    draw_h = end_row - start_row
    if draw_w <= 0 or draw_h <= 0: return

    if not hasattr(framebuffer, '_cached_bpp'):
        framebuffer._cached_bpp = framebuffer.bytes_per_pixel if hasattr(framebuffer, 'bytes_per_pixel') else 2
    dest_bpp = framebuffer._cached_bpp

    p_dest = _as_ptr16(framebuffer) if dest_bpp == 2 else _as_ptr8(framebuffer)
    d_off = (y + start_row) * fb_width + x + left_clip

    micropython.heap_lock()
    try:
        if dest_bpp == 2:
            _fill_rows_rgb565_viper(p_dest, d_off, fb_width, draw_w, draw_h, bg_pixel)
        elif dest_bpp == 1:
            _fill_rows_8bit_viper(p_dest, d_off, fb_width, draw_w, draw_h, bg_pixel)
        else:
            raise ValueError(f"Unsupported fill: dest_bpp={dest_bpp}")
    finally:
        micropython.heap_unlock()

def composite_region(framebuffer, fb_width, fb_height, bytes_per_pixel, fh, header_bytes, src_row_bytes,
                     sx, sy, sw, sh, cell_x, cell_y, cell_w, cell_h, glyph_x, glyph_y,
                     buffer, palette, bg_pixel, clip=None):
    if cell_w <= 0 or cell_h <= 0: return

    min_x, min_y = 0, 0
    max_x, max_y = fb_width, fb_height
    if clip:
        ccx, ccy, ccw, cch = clip
        min_x, min_y = max(min_x, ccx), max(min_y, ccy)
        max_x, max_y = min(max_x, ccx + ccw), min(max_y, ccy + cch)

    if cell_x >= max_x or cell_y >= max_y: return
    if cell_x + cell_w <= min_x or cell_y + cell_h <= min_y: return

    start_row = max(0, min_y - cell_y)
    end_row = min(cell_h, max_y - cell_y)
    left_clip = max(0, min_x - cell_x)
    right_clip = max(0, cell_x + cell_w - max_x)
    draw_w = cell_w - left_clip - right_clip
    if draw_w <= 0: return

    if not hasattr(framebuffer, '_cached_bpp'):
        framebuffer._cached_bpp = framebuffer.bytes_per_pixel if hasattr(framebuffer, 'bytes_per_pixel') else 2
    dest_bpp = framebuffer._cached_bpp

    glyph_start = glyph_y
    glyph_end = glyph_y + sh
    row_top = max(start_row, glyph_start)
    row_bottom = min(end_row, glyph_end)

    if row_top > start_row:
        fill_region(framebuffer, fb_width, fb_height,
                    cell_x + left_clip, cell_y + start_row, draw_w, row_top - start_row,
                    bg_pixel)
    if row_bottom < end_row:
        fill_region(framebuffer, fb_width, fb_height,
                    cell_x + left_clip, cell_y + row_bottom, draw_w, end_row - row_bottom,
                    bg_pixel)
    if row_bottom <= row_top:
        return

    p_dest = _as_ptr16(framebuffer) if dest_bpp == 2 else _as_ptr8(framebuffer)
    p_pal = _as_ptr16(palette) if (dest_bpp == 2 and palette is not None) else (_as_ptr8(palette) if palette is not None else None)

    stride_bytes = src_row_bytes
    if buffer is not None and isinstance(buffer, memoryview) and len(buffer) >= stride_bytes:
        batch_buf = buffer
    elif buffer is not None and len(buffer) >= stride_bytes:
        batch_buf = memoryview(buffer)
    else:
        global _scratch_buf, _scratch_view
        if _scratch_buf is None or len(_scratch_buf) < stride_bytes:
            _scratch_buf = bytearray(stride_bytes)
            _scratch_view = memoryview(_scratch_buf)
        batch_buf = _scratch_view
    p_src = _as_ptr8(batch_buf)
    rows_per_batch = len(batch_buf) // stride_bytes
    if rows_per_batch < 1: rows_per_batch = 1

    left_w = glyph_x - left_clip
    src_x = sx
    glyph_w_visible = sw
    if left_w < 0:
        src_x = sx - left_w
        glyph_w_visible = sw + left_w
        left_w = 0
    if glyph_w_visible < 0: glyph_w_visible = 0
    right_w = draw_w - left_w - glyph_w_visible
    if right_w < 0:
        glyph_w_visible += right_w
        right_w = 0
    if glyph_w_visible < 0: glyph_w_visible = 0

    row = row_top
    while row < row_bottom:
        this_h = min(rows_per_batch, row_bottom - row)
        nbytes = this_h * stride_bytes
        fh.seek(header_bytes + (sy + (row - glyph_start)) * stride_bytes)
        if IS_MICROPYTHON:
            fh.readinto(batch_buf, nbytes)
        else:
            batch_buf[:nbytes] = fh.read(nbytes)

        d_off = (cell_y + row) * fb_width + cell_x + left_clip

        micropython.heap_lock()
        try:
            if dest_bpp == 2:
                _composite_glyph_row_gs8_to_rgb565_viper(p_dest, d_off, fb_width, p_src, src_x, stride_bytes,
                                                          left_w, glyph_w_visible, right_w, this_h, p_pal, bg_pixel)
            elif dest_bpp == 1:
                _composite_glyph_row_gs8_to_8bit_viper(p_dest, d_off, fb_width, p_src, src_x, stride_bytes,
                                                        left_w, glyph_w_visible, right_w, this_h, p_pal, bg_pixel)
            else:
                raise ValueError(f"Unsupported composite: dest_bpp={dest_bpp}")
        finally:
            micropython.heap_unlock()

        row += this_h

def blit_region(framebuffer, fb_width, fb_height, bytes_per_pixel, fh, header_bytes, src_row_bytes,
                sx, sy, sw, sh, dx, dy, buffer=None, src_format=None, palette=None, clip=None, key=-1):
    """ Standard high-performance blit from flash to framebuffer. """
    if sw <= 0 or sh <= 0: return

    min_x, min_y = 0, 0
    max_x, max_y = fb_width, fb_height
    if clip:
        cx, cy, cw, ch = clip
        min_x, min_y = max(min_x, cx), max(min_y, cy)
        max_x, max_y = min(max_x, cx + cw), min(max_y, cy + ch)

    if dx >= max_x or dy >= max_y: return
    if dx + sw <= min_x or dy + sh <= min_y: return

    start_row = max(0, min_y - dy)
    end_row = min(sh, max_y - dy)
    left_clip = max(0, min_x - dx)
    right_clip = max(0, dx + sw - max_x)
    copy_width = sw - left_clip - right_clip
    if copy_width <= 0: return

    if src_format is None:
        src_fmt = 1 if bytes_per_pixel == 2 else 6
    else:
        src_fmt = src_format

    src_bpp = 2 if src_fmt == 1 else 1

    stride_bytes = src_row_bytes
    if buffer is not None and isinstance(buffer, memoryview) and len(buffer) >= stride_bytes:
        batch_buf = buffer
    elif buffer is not None and len(buffer) >= stride_bytes:
        batch_buf = memoryview(buffer)
    else:
        global _scratch_buf, _scratch_view
        if _scratch_buf is None or len(_scratch_buf) < stride_bytes:
            _scratch_buf = bytearray(stride_bytes)
            _scratch_view = memoryview(_scratch_buf)
        batch_buf = _scratch_view
    rows_per_batch = len(batch_buf) // stride_bytes

    if not hasattr(framebuffer, '_cached_bpp'):
        framebuffer._cached_bpp = framebuffer.bytes_per_pixel if hasattr(framebuffer, 'bytes_per_pixel') else 2
    dest_bpp = framebuffer._cached_bpp

    p_dest = _as_ptr16(framebuffer) if dest_bpp == 2 else _as_ptr8(framebuffer)
    p_pal = _as_ptr16(palette) if (dest_bpp == 2 and palette is not None) else (_as_ptr8(palette) if palette is not None else None)
    p_src = _as_ptr16(batch_buf) if src_bpp == 2 else _as_ptr8(batch_buf)

    s_col = sx + left_clip
    s_stride = stride_bytes // src_bpp

    fh.seek(header_bytes + (sy + start_row) * stride_bytes)

    d_off = (dy + start_row) * fb_width + dx + left_clip
    current_row = start_row
    while current_row < end_row:
        this_batch_h = min(rows_per_batch, end_row - current_row)
        nbytes = this_batch_h * stride_bytes

        if IS_MICROPYTHON:
            fh.readinto(batch_buf, nbytes)
        else:
            batch_buf[:nbytes] = fh.read(nbytes)

        micropython.heap_lock()
        try:
            if dest_bpp == 2:
                if src_fmt == 6:
                    if p_pal is not None:
                        _blit_rect_gs8_to_rgb565_viper(p_dest, d_off, fb_width, p_src, s_col, s_stride, copy_width, this_batch_h, p_pal, key)
                    else:
                        _blit_rect_gs8_to_rgb565_direct_viper(p_dest, d_off, fb_width, p_src, s_col, s_stride, copy_width, this_batch_h, key)
                elif src_fmt == 1:
                    _blit_rect_rgb565_to_rgb565_viper(p_dest, d_off, fb_width, p_src, s_col, s_stride, copy_width, this_batch_h, key)
            elif dest_bpp == 1:
                if src_fmt == 6:
                    if p_pal is not None:
                        _blit_rect_gs8_to_8bit_palette_viper(p_dest, d_off, fb_width, p_src, s_col, s_stride, copy_width, this_batch_h, p_pal, key)
                    else:
                        _blit_rect_8bit_to_8bit_viper(p_dest, d_off, fb_width, p_src, s_col, s_stride, copy_width, this_batch_h, key)
            else:
                raise ValueError(f"Unsupported blit: dest_bpp={dest_bpp} src_fmt={src_fmt}")
        finally:
            micropython.heap_unlock()

        d_off += this_batch_h * fb_width
        current_row += this_batch_h
