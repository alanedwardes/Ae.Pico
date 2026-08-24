import struct
import gc
import sys

try:
    import micropython
    IS_MICROPYTHON = sys.implementation.name == 'micropython'
except ImportError:
    IS_MICROPYTHON = False

if not IS_MICROPYTHON:
    class micropython:
        @staticmethod
        def heap_lock(): pass
        @staticmethod
        def heap_unlock(): pass

from bitblt import render_glyph_cell, fill_region, _as_ptr16, _as_ptr8

# Glyphs are stored compactly in a bytearray to minimize RAM.
# Packed layout (little-endian): x,y,width,height (uint16), xoffset,yoffset,xadvance (int16), page (uint8)
_GLYPH_FMT = '<HHHHhhhB'
_GLYPH_SIZE = struct.calcsize(_GLYPH_FMT)

def _build_palette_bytes(tint_color, bytes_per_pixel):
    """Build a 256x1 palette as bytes for GS8 source, scaled to the destination bit depth."""
    if tint_color is None or not isinstance(tint_color, int):
        r, g, b = 255, 255, 255
    else:
        r = (tint_color >> 16) & 0xFF
        g = (tint_color >> 8) & 0xFF
        b = tint_color & 0xFF

    if bytes_per_pixel == 2:
        pal = bytearray(256 * 2)
        o = 0
        for i in range(256):
            tr = (r * i) // 255
            tg = (g * i) // 255
            tb = (b * i) // 255
            val = ((tr & 0xF8) << 8) | ((tg & 0xFC) << 3) | (tb >> 3)
            pal[o] = val & 0xFF
            pal[o + 1] = (val >> 8) & 0xFF
            o += 2
    else:
        pal = bytearray(256)
        for i in range(256):
            tr = (r * i) // 255
            tg = (g * i) // 255
            tb = (b * i) // 255
            val = (tr & 0xE0) | ((tg & 0xE0) >> 3) | ((tb & 0xC0) >> 6)
            pal[i] = val
    return pal

_PALETTE_CACHE = {}
_PALETTE_CACHE_LIMIT = 16

# Hoisted: building this tuple inline would allocate on every draw_text call
_PAGE_CONTAINERS = (dict, list, tuple)

def _resolve_palette(tint_color, bytes_per_pixel):
    tint = tint_color if isinstance(tint_color, int) else 0xFFFFFF
    # int key instead of a tuple: fits a small int, so the cache-hit path
    # (every draw_text call) doesn't allocate
    cache_key = (tint << 1) | (bytes_per_pixel - 1)
    pal = _PALETTE_CACHE.get(cache_key)
    if pal is not None: return pal
    pal = _build_palette_bytes(tint, bytes_per_pixel)
    if len(_PALETTE_CACHE) >= _PALETTE_CACHE_LIMIT:
        try: _PALETTE_CACHE.pop(next(iter(_PALETTE_CACHE)))
        except StopIteration: pass
    _PALETTE_CACHE[cache_key] = pal
    return pal

class BMFont:
    def __init__(self):
        self.line_height = 0
        self.base = 0
        self.scale_w = 0
        self.scale_h = 0
        self.pages = {}
        self.chars = {}  # maps codepoint -> offset into _glyph_data
        self.kerning = {}  # optional; only populated when requested
        self._glyph_data = bytearray()
        self._char_off = bytearray(b'\xff\xff' * 256)

    @staticmethod
    def _dequote(s):
        if s and len(s) >= 2 and s[0] == '"' and s[-1] == '"':
            return s[1:-1]
        return s  

    @classmethod
    def load(cls, path, load_kerning=False):
        font = cls()
        glyph_count = 0  # number of chars actually written into _glyph_data so far
        with open(path, "r") as f:
            for i, line in enumerate(f):
                if (i & 31) == 0:
                    gc.collect()
                line = line.strip()
                if not line:
                    continue
                parts = line.split()
                kind = parts[0]
                args = {}
                for token in parts[1:]:
                    if "=" in token:
                        k, v = token.split("=", 1)
                        args[k] = v
                if kind == "common":
                    font.line_height = int(args.get("lineHeight", 0))
                    font.base = int(args.get("base", 0))
                    font.scale_w = int(args.get("scaleW", 0))
                    font.scale_h = int(args.get("scaleH", 0))
                elif kind == "chars":
                    # The .fnt format declares the total char count before
                    # any "char" lines -- pre-allocate _glyph_data to its
                    # final size ONCE instead of growing it one glyph at a
                    # time via .extend(). This allocator has no in-place
                    # grow: every .extend() call on a bytearray reallocates
                    # and copies the WHOLE buffer so far, so loading an
                    # N-glyph font the naive way costs N reallocations of
                    # monotonically increasing size, each discarding the
                    # previous (now-fragmenting) block.
                    declared_count = int(args.get("count", 0))
                    if declared_count > 0:
                        font._glyph_data = bytearray(declared_count * _GLYPH_SIZE)
                elif kind == "page":
                    pid = int(args.get("id", 0))
                    fname = cls._dequote(args.get("file", ""))
                    font.pages[pid] = fname
                elif kind == "char":
                    char_id = int(args.get("id", 0))
                    x = int(args.get("x", 0))
                    y = int(args.get("y", 0))
                    width = int(args.get("width", 0))
                    height = int(args.get("height", 0))
                    xoffset = int(args.get("xoffset", 0))
                    yoffset = int(args.get("yoffset", 0))
                    xadvance = int(args.get("xadvance", 0))
                    page = int(args.get("page", 0))
                    # Write directly into the pre-sized buffer (no per-glyph
                    # allocation). Falls back to .extend() only if the
                    # "chars count=" line was missing/wrong and we've run
                    # past the pre-allocated capacity -- rare, and no worse
                    # than the old behavior for that case.
                    off = glyph_count * _GLYPH_SIZE
                    packed = struct.pack(_GLYPH_FMT,
                        x, y, width, height, xoffset, yoffset, xadvance, page)
                    if off + _GLYPH_SIZE <= len(font._glyph_data):
                        font._glyph_data[off:off + _GLYPH_SIZE] = packed
                    else:
                        font._glyph_data.extend(packed)
                    font.chars[char_id] = off
                    if char_id < 256:
                        struct.pack_into('<H', font._char_off, char_id * 2, off)
                    glyph_count += 1
                elif kind == "kerning" and load_kerning:
                    first = int(args.get("first", 0))
                    second = int(args.get("second", 0))
                    amount = int(args.get("amount", 0))
                    font.kerning[(first, second)] = amount
        return font

def draw_text(framebuffer, display_width, display_height, font: BMFont, page_files, text, x, y, kerning=False, scale_up=1, scale_down=1, color=None, linebuf=None, clip=None, background=None, top_edge=True, bottom_edge=True):
    # GS8 source atlases: one byte per pixel per row
    row_bytes = font.scale_w
    
    # Detemine destination pixel depth
    bytes_per_pixel = framebuffer.bytes_per_pixel if hasattr(framebuffer, 'bytes_per_pixel') else 2
    
    # Resolve tinted palette for font rendering (GS8 -> Dest)
    palette = _resolve_palette(color, bytes_per_pixel)
    bg_pixel = None
    if background is not None:
        bg_pal = _resolve_palette(background, bytes_per_pixel)
        bg_pixel = (bg_pal[510] | (bg_pal[511] << 8)) if bytes_per_pixel == 2 else bg_pal[255]

    # Dicts keyed by page id and lists/tuples index identically via
    # pages[page], so pass them through rather than rebuilding a dict on
    # every call (this runs per textbox line on the board).
    if isinstance(page_files, _PAGE_CONTAINERS):
        pages = page_files
    else:
        pages = (page_files,)

    # Optimization: pre-index glyph data for faster access
    glyph_data = font._glyph_data
    
    # Scale fast path
    is_scaled = (scale_up != 1 or scale_down != 1)

    if background is not None and clip:
        box_x, box_y, box_w, box_h = clip
        box_right = box_x + box_w
        box_bottom = box_y + box_h
        total_lines = text.count("\n") + 1
        line_h_px = (font.line_height * scale_up) // scale_down if is_scaled else font.line_height
        watermark_x = box_x
    else:
        box_x = None
    line_idx = 0
    n = len(text)

    cx, cy = x, y
    prev_id = None
    for i in range(n):
        ch = text[i]
        if ch == "\n":
            if box_x is not None:
                fill_y = box_y if (line_idx == 0 and top_edge) else cy
                fill_bottom = box_bottom if (line_idx == total_lines - 1 and bottom_edge) else cy + line_h_px
                fill_region(framebuffer, display_width, display_height,
                            watermark_x, fill_y, box_right - watermark_x, fill_bottom - fill_y,
                            bg_pixel, clip)
                watermark_x = box_x
            cx, cy = x, cy + font.line_height; prev_id = None; line_idx += 1
            continue
        code = ord(ch)
        off = font.chars.get(code)
        if off is None: prev_id = None; continue
        if prev_id is not None and kerning and font.kerning:
            cx += font.kerning.get((prev_id, code), 0)

        # Unpack glyph data: manual unpack (faster than struct in uPy): <HHHHhhhB (15 bytes)
        # 0: src_x (H), 2: src_y (H), 4: width (H), 6: height (H), 8: xoffset (h), 10: yoffset (h), 12: xadvance (h), 14: page (B)
        src_x = glyph_data[off] | (glyph_data[off+1] << 8)
        src_y = glyph_data[off+2] | (glyph_data[off+3] << 8)
        width = glyph_data[off+4] | (glyph_data[off+5] << 8)
        height = glyph_data[off+6] | (glyph_data[off+7] << 8)

        xo = glyph_data[off+8] | (glyph_data[off+9] << 8)
        if xo > 32767: xo -= 65536
        yo = glyph_data[off+10] | (glyph_data[off+11] << 8)
        if yo > 32767: yo -= 65536
        xa = glyph_data[off+12] | (glyph_data[off+13] << 8)
        if xa > 32767: xa -= 65536
        page = glyph_data[off+14]

        if is_scaled:
            dest_x = cx + (xo * scale_up) // scale_down
            dest_y = cy + (yo * scale_up) // scale_down
            adv_px = (xa * scale_up) // scale_down
        else:
            dest_x = cx + xo
            dest_y = cy + yo
            adv_px = xa

        if background is not None and box_x is not None:
            fill_x = watermark_x
            if dest_x < fill_x: fill_x = dest_x
            ink_right = dest_x + width
            fill_right = cx + adv_px
            if ink_right > fill_right: fill_right = ink_right
            fill_y = box_y if (line_idx == 0 and top_edge) else cy
            fill_bottom = box_bottom if (line_idx == total_lines - 1 and bottom_edge) else cy + line_h_px
            if fill_right > fill_x and fill_bottom > fill_y:
                render_glyph_cell(framebuffer, display_width, display_height, bytes_per_pixel,
                                  pages[page], 4, row_bytes,
                                  src_x, src_y, width, height,
                                  fill_x, fill_y, fill_right - fill_x, fill_bottom - fill_y,
                                  dest_x - fill_x, dest_y - fill_y,
                                  linebuf, palette, bg_pixel, clip)
            watermark_x = fill_right
        else:
            # Quick bounds check (rejection) before calling render_glyph_cell.
            # Positional args throughout: keyword calls build a dict per
            # glyph in MicroPython, and this runs for every character drawn.
            if dest_x >= display_width or dest_y >= display_height: pass
            elif dest_x + width <= 0 or dest_y + height <= 0: pass
            else:
                render_glyph_cell(framebuffer, display_width, display_height, bytes_per_pixel,
                            pages[page], 4, row_bytes,
                            src_x, src_y, width, height,
                            dest_x, dest_y, width, height, 0, 0,
                            linebuf, palette, None, clip)

        cx += adv_px
        prev_id = code

    if background is not None and box_x is not None:
        fill_y = box_y if (line_idx == 0 and top_edge) else cy
        fill_bottom = box_bottom if (line_idx == total_lines - 1 and bottom_edge) else cy + line_h_px
        fill_region(framebuffer, display_width, display_height,
                    watermark_x, fill_y, box_right - watermark_x, fill_bottom - fill_y,
                    bg_pixel, clip)

_MISSING = 65535
_CODE_MASK = 0x1FFFFF
_MEASURE_OUT = bytearray(16)

def _decode_codepoint(text, i):
    b0 = text[i]
    if b0 < 0x80:
        return (1 << 21) | b0
    if b0 < 0xE0:
        return (2 << 21) | ((b0 & 0x1F) << 6) | (text[i + 1] & 0x3F)
    if b0 < 0xF0:
        return (3 << 21) | ((b0 & 0x0F) << 12) | ((text[i + 1] & 0x3F) << 6) | (text[i + 2] & 0x3F)
    return (4 << 21) | ((b0 & 0x07) << 18) | ((text[i + 1] & 0x3F) << 12) | ((text[i + 2] & 0x3F) << 6) | (text[i + 3] & 0x3F)

if IS_MICROPYTHON:
    @micropython.viper
    def _decode_codepoint_viper(text: ptr8, i: int) -> int:
        b0 = text[i]
        if b0 < 0x80:
            return (1 << 21) | b0
        if b0 < 0xE0:
            return (2 << 21) | ((b0 & 0x1F) << 6) | (text[i + 1] & 0x3F)
        if b0 < 0xF0:
            return (3 << 21) | ((b0 & 0x0F) << 12) | ((text[i + 1] & 0x3F) << 6) | (text[i + 2] & 0x3F)
        return (4 << 21) | ((b0 & 0x07) << 18) | ((text[i + 1] & 0x3F) << 12) | ((text[i + 2] & 0x3F) << 6) | (text[i + 3] & 0x3F)

    @micropython.viper
    def _measure_text_viper(glyph_data: ptr8, text: ptr8, n: int, line_height: int, char_off: ptr16, out: ptr32) -> int:
        cx = 0
        cy = 0
        found = 0
        min_left = 0
        min_top = 0
        max_right = 0
        max_bottom = 0
        i = 0
        while i < n:
            packed = int(_decode_codepoint_viper(text, i))
            code = packed & 0x1FFFFF
            i += packed >> 21
            if code == 10:
                cx = 0
                cy += line_height
                continue
            if code < 256:
                off = char_off[code]
            else:
                off = 65535
            if off == 65535:
                continue
            width = glyph_data[off+4] | (glyph_data[off+5] << 8)
            height = glyph_data[off+6] | (glyph_data[off+7] << 8)
            xoffset = glyph_data[off+8] | (glyph_data[off+9] << 8)
            if xoffset > 32767: xoffset -= 65536
            yoffset = glyph_data[off+10] | (glyph_data[off+11] << 8)
            if yoffset > 32767: yoffset -= 65536
            xadvance = glyph_data[off+12] | (glyph_data[off+13] << 8)
            if xadvance > 32767: xadvance -= 65536
            glyph_left = cx + xoffset
            glyph_top = cy + yoffset
            glyph_right = glyph_left + width
            glyph_bottom = glyph_top + height
            if found == 0:
                min_left = glyph_left
                min_top = glyph_top
                max_right = glyph_right
                max_bottom = glyph_bottom
            else:
                if glyph_left < min_left: min_left = glyph_left
                if glyph_top < min_top: min_top = glyph_top
                if glyph_right > max_right: max_right = glyph_right
                if glyph_bottom > max_bottom: max_bottom = glyph_bottom
            found = 1
            cx += xadvance
        if found == 0:
            return 0
        out[0] = max_right - min_left
        out[1] = max_bottom - min_top
        out[2] = min_left
        out[3] = min_top
        return 1

    @micropython.viper
    def _measure_extend_viper(glyph_data: ptr8, text: ptr8, n: int, cx_in: int, prev_id_in: int, found_in: int, min_left_in: int, max_right_in: int, char_off: ptr16, out: ptr32) -> int:
        cx = cx_in
        prev_id = prev_id_in
        found = found_in
        min_left = min_left_in
        max_right = max_right_in
        i = 0
        while i < n:
            packed = int(_decode_codepoint_viper(text, i))
            code = packed & 0x1FFFFF
            i += packed >> 21
            if code == 10:
                cx = 0
                prev_id = -1
                continue
            if code < 256:
                off = char_off[code]
            else:
                off = 65535
            if off == 65535:
                prev_id = -1
                continue
            width = glyph_data[off+4] | (glyph_data[off+5] << 8)
            xoffset = glyph_data[off+8] | (glyph_data[off+9] << 8)
            if xoffset > 32767: xoffset -= 65536
            xadvance = glyph_data[off+12] | (glyph_data[off+13] << 8)
            if xadvance > 32767: xadvance -= 65536
            glyph_left = cx + xoffset
            glyph_right = glyph_left + width
            if found == 0:
                min_left = glyph_left
                max_right = glyph_right
            else:
                if glyph_left < min_left: min_left = glyph_left
                if glyph_right > max_right: max_right = glyph_right
            found = 1
            cx += xadvance
            prev_id = code
        out[0] = cx
        out[1] = prev_id
        out[2] = min_left
        out[3] = max_right
        return found
else:
    _decode_codepoint_viper = None
    _measure_text_viper = None
    _measure_extend_viper = None


def _measure_text_pure(font, text, kerning):
    max_right = None
    max_bottom = None
    min_left = None
    min_top = None
    cx = 0
    cy = 0
    prev_id = None
    glyph_data = font._glyph_data
    micropython.heap_lock()
    try:
        i = 0
        n = len(text)
        while i < n:
            packed = _decode_codepoint(text, i)
            code = packed & _CODE_MASK
            i += packed >> 21
            if code == 10:
                cx = 0
                cy += font.line_height
                prev_id = None
                continue
            off = font.chars.get(code)
            if off is None:
                prev_id = None
                continue
            if prev_id is not None and kerning and font.kerning:
                cx += font.kerning.get((prev_id, code), 0)
            width = glyph_data[off+4] | (glyph_data[off+5] << 8)
            height = glyph_data[off+6] | (glyph_data[off+7] << 8)
            xoffset = glyph_data[off+8] | (glyph_data[off+9] << 8)
            if xoffset > 32767: xoffset -= 65536
            yoffset = glyph_data[off+10] | (glyph_data[off+11] << 8)
            if yoffset > 32767: yoffset -= 65536
            xadvance = glyph_data[off+12] | (glyph_data[off+13] << 8)
            if xadvance > 32767: xadvance -= 65536
            glyph_left = cx + xoffset
            glyph_top = cy + yoffset
            glyph_right = glyph_left + width
            glyph_bottom = glyph_top + height
            if min_left is None or glyph_left < min_left:
                min_left = glyph_left
            if min_top is None or glyph_top < min_top:
                min_top = glyph_top
            if max_right is None or glyph_right > max_right:
                max_right = glyph_right
            if max_bottom is None or glyph_bottom > max_bottom:
                max_bottom = glyph_bottom
            cx += xadvance
            prev_id = code
    finally:
        micropython.heap_unlock()
    if min_left is None:
        return 0, 0, 0, 0
    return max_right - min_left, max_bottom - min_top, min_left, min_top


def _measure_extend_pure(font, text, cx, prev_id, min_left, max_right, kerning):
    glyph_data = font._glyph_data
    micropython.heap_lock()
    try:
        i = 0
        n = len(text)
        while i < n:
            packed = _decode_codepoint(text, i)
            code = packed & _CODE_MASK
            i += packed >> 21
            if code == 10:
                cx = 0
                prev_id = None
                continue
            off = font.chars.get(code)
            if off is None:
                prev_id = None
                continue
            if prev_id is not None and kerning and font.kerning:
                cx += font.kerning.get((prev_id, code), 0)
            width = glyph_data[off+4] | (glyph_data[off+5] << 8)
            xoffset = glyph_data[off+8] | (glyph_data[off+9] << 8)
            if xoffset > 32767: xoffset -= 65536
            xadvance = glyph_data[off+12] | (glyph_data[off+13] << 8)
            if xadvance > 32767: xadvance -= 65536
            glyph_left = cx + xoffset
            glyph_right = glyph_left + width
            if min_left is None or glyph_left < min_left:
                min_left = glyph_left
            if max_right is None or glyph_right > max_right:
                max_right = glyph_right
            cx += xadvance
            prev_id = code
    finally:
        micropython.heap_unlock()
    return cx, prev_id, min_left, max_right


def measure_text(font: BMFont, text: bytes, kerning=False):
    """Return (width, height, min_x, min_y) tight bounds of the rendered text."""
    if IS_MICROPYTHON and not kerning:
        micropython.heap_lock()
        try:
            found = _measure_text_viper(font._glyph_data, text, len(text), font.line_height, font._char_off, _MEASURE_OUT)
        finally:
            micropython.heap_unlock()
        if not found:
            return 0, 0, 0, 0
        w, h, min_left, min_top = struct.unpack('<iiii', _MEASURE_OUT)
        return w, h, min_left, min_top
    return _measure_text_pure(font, text, kerning)


def measure_extend(font: BMFont, text: bytes, cx, prev_id, min_left, max_right, kerning=False):
    if IS_MICROPYTHON and not kerning:
        prev_id_in = -1 if prev_id is None else prev_id
        found_in = 0 if min_left is None else 1
        min_left_in = 0 if min_left is None else min_left
        max_right_in = 0 if max_right is None else max_right
        micropython.heap_lock()
        try:
            found = _measure_extend_viper(font._glyph_data, text, len(text), cx, prev_id_in, found_in, min_left_in, max_right_in, font._char_off, _MEASURE_OUT)
        finally:
            micropython.heap_unlock()
        cx_out, prev_id_out, min_left_out, max_right_out = struct.unpack('<iiii', _MEASURE_OUT)
        prev_id = None if prev_id_out == -1 else prev_id_out
        if not found:
            return cx_out, prev_id, None, None
        return cx_out, prev_id, min_left_out, max_right_out
    return _measure_extend_pure(font, text, cx, prev_id, min_left, max_right, kerning)
