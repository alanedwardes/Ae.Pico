import sys
import struct

try:
    import micropython
    IS_MICROPYTHON = sys.implementation.name == 'micropython'
except ImportError:
    IS_MICROPYTHON = False

if not IS_MICROPYTHON:
    # CPython Mocking logic for simulator
    class micropython:
        @staticmethod
        def viper(f): return f
        @staticmethod
        def native(f): return f
        @staticmethod
        def const(x): return x
    
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
    # MicroPython: Handle wrappers or return raw objects for Viper
    def _as_ptr16(obj):
        if hasattr(obj, '_framebuffer'): return obj._framebuffer
        if hasattr(obj, '_buf'): return obj._buf
        return obj
    def _as_ptr8(obj):
        if hasattr(obj, '_framebuffer'): return obj._framebuffer
        if hasattr(obj, '_buf'): return obj._buf
        return obj

# --- Optimized Viper Paths ---

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

# --- Main Blit API ---

def blit_region(framebuffer, fb_width, fb_height, bytes_per_pixel, fh, header_bytes, src_row_bytes,
                sx, sy, sw, sh, dx, dy, buffer=None, src_format=None, palette=None, clip=None, key=-1):
    """ Standard high-performance blit from flash to framebuffer. """
    if sw <= 0 or sh <= 0: return
        
    # 1. Coordinate Clipping
    min_x, min_y = 0, 0
    max_x, max_y = fb_width, fb_height
    if clip:
        cx, cy, cw, ch = clip
        min_x, min_y = max(min_x, cx), max(min_y, cy)
        max_x, max_y = min(max_x, cx + cw), min(max_y, cy + ch)
        
    if dx >= max_x or dy >= max_y: return
    if dx + sw <= min_x or dy + sh <= min_y: return

    # Clipping to region
    start_row = max(0, min_y - dy)
    end_row = min(sh, max_y - dy)
    left_clip = max(0, min_x - dx)
    right_clip = max(0, dx + sw - max_x)
    copy_width = sw - left_clip - right_clip
    if copy_width <= 0: return

    # 2. Format Detection
    # 2. Format Detection
    if src_format is None:
        src_fmt = 1 if bytes_per_pixel == 2 else 6
    else:
        src_fmt = src_format
        
    src_bpp = 2 if src_fmt == 1 else 1 
    row_size = copy_width * src_bpp
    
    # 3. Buffer Management with Row Batching
    if buffer is None or len(buffer) < row_size:
        batch_buf = memoryview(bytearray(row_size))
        rows_per_batch = 1
    else:
        batch_buf = memoryview(buffer)
        rows_per_batch = len(batch_buf) // row_size

    # Optimization: Cache dest_bpp and pointers once outside the loop
    if not hasattr(framebuffer, '_cached_bpp'):
        framebuffer._cached_bpp = framebuffer.bytes_per_pixel if hasattr(framebuffer, 'bytes_per_pixel') else 2
    dest_bpp = framebuffer._cached_bpp

    p_dest = _as_ptr16(framebuffer) if dest_bpp == 2 else _as_ptr8(framebuffer)
    p_pal = _as_ptr16(palette) if (dest_bpp == 2 and palette is not None) else (_as_ptr8(palette) if palette is not None else None)

    current_row = start_row
    while current_row < end_row:
        this_batch_h = min(rows_per_batch, end_row - current_row)
        
        # Load batch rows from flash
        current_pos = -1
        for i in range(this_batch_h):
            r_idx = current_row + i
            src_offset = header_bytes + (sy + r_idx) * src_row_bytes + (sx + left_clip) * src_bpp
            if current_pos != src_offset:
                fh.seek(src_offset)
            
            target = batch_buf[i * row_size : (i + 1) * row_size]
            if IS_MICROPYTHON:
                fh.readinto(target)
            else:
                target[:row_size] = fh.read(row_size)
            current_pos = src_offset + row_size

        # 4. Fast Path Dispatch
        d_fb_x = dx + left_clip
        d_fb_y = dy + current_row
        
        # 4. Fast Path Dispatch
        d_fb_x = dx + left_clip
        d_fb_y = dy + current_row
        d_off = d_fb_y * fb_width + d_fb_x

        if dest_bpp == 2:
            if src_fmt == 6: # GS8 -> RGB565
                p_src = _as_ptr8(batch_buf)
                if p_pal is not None:
                    _blit_rect_gs8_to_rgb565_viper(p_dest, d_off, fb_width, p_src, 0, copy_width, copy_width, this_batch_h, p_pal, key)
                else:
                    _blit_rect_gs8_to_rgb565_direct_viper(p_dest, d_off, fb_width, p_src, 0, copy_width, copy_width, this_batch_h, key)
            elif src_fmt == 1: # RGB565 -> RGB565
                p_src = _as_ptr16(batch_buf)
                _blit_rect_rgb565_to_rgb565_viper(p_dest, d_off, fb_width, p_src, 0, copy_width, copy_width, this_batch_h, key)
        elif dest_bpp == 1:
            if src_fmt == 6: # 8-bit (GS8/RGB332) -> 8-bit
                p_src = _as_ptr8(batch_buf)
                if p_pal is not None:
                    _blit_rect_gs8_to_8bit_palette_viper(p_dest, d_off, fb_width, p_src, 0, copy_width, copy_width, this_batch_h, p_pal, key)
                else:
                    _blit_rect_8bit_to_8bit_viper(p_dest, d_off, fb_width, p_src, 0, copy_width, copy_width, this_batch_h, key)
        else:
            raise ValueError(f"Unsupported blit: dest_bpp={dest_bpp} src_fmt={src_fmt}")

        current_row += this_batch_h
