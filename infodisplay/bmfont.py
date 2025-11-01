import struct
import gc
import framebuf
try:
    import micropython
except ImportError:  # Allow importing under CPython tooling
    micropython = None

# Glyphs are stored compactly in a bytearray to minimize RAM.
# Packed layout (little-endian): x,y,width,height (uint16), xoffset,yoffset,xadvance (int16), page (uint8)
_GLYPH_FMT = '<HHHHhhhB'

def _build_tint_lut_bytes(color565):
    """Build a compact 128B LUT (little-endian RGB565 pairs) for 6-bit intensity.

    Source atlas assumed grayscale (intensity in green channel)."""
    r5 = (color565 >> 11) & 0x1F
    g6 = (color565 >> 5) & 0x3F
    b5 = color565 & 0x1F
    lut = bytearray(128)
    o = 0
    for i in range(64):
        tr = (r5 * i) // 63
        tg = (g6 * i) // 63
        tb = (b5 * i) // 63
        tp = (tr << 11) | (tg << 5) | tb
        lut[o] = tp & 0xFF
        lut[o + 1] = (tp >> 8) & 0xFF
        o += 2
    return lut


def _rgb565_from_tuple(r, g, b):
    return ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)


if micropython:
    @micropython.viper
    def _tint_line(linebuf: ptr8, length: int, lut: ptr8):
        n: int = 0
        while n < length:
            b0 = linebuf[n]
            b1 = linebuf[n + 1]
            px = int(b0) | (int(b1) << 8)
            intensity = (px >> 5) & 0x3F  # use green channel for grayscale intensity
            li = intensity << 1
            linebuf[n] = lut[li]
            linebuf[n + 1] = lut[li + 1]
            n += 2
else:
    def _tint_line(linebuf, length, lut):
        lb = linebuf
        for i in range(0, length, 2):
            px = lb[i] | (lb[i + 1] << 8)
            intensity = (px >> 5) & 0x3F
            li = intensity * 2
            lb[i] = lut[li]
            lb[i + 1] = lut[li + 1]


def blit_region(framebuffer, fb_width, fb_height, bytes_per_pixel, fh, src_row_bytes,
               sx, sy, sw, sh, dx, dy, tint_color=None):
    if sw <= 0 or sh <= 0:
        return
    if dx >= fb_width or dy >= fb_height:
        return
    if dx + sw <= 0 or dy + sh <= 0:
        return

    start_row = max(0, -dy)
    end_row = min(sh, fb_height - dy)

    left_clip = max(0, -dx)
    right_clip = max(0, dx + sw - fb_width)
    copy_width = sw - left_clip - right_clip
    if copy_width <= 0:
        return

    src_x = sx + left_clip
    fb_x = dx + left_clip
    linebuf = bytearray(copy_width * bytes_per_pixel)

    # Prepare tint LUT if requested
    tint_lut = None
    if tint_color is not None:
        if isinstance(tint_color, tuple):
            tint_color = _rgb565_from_tuple(tint_color[0], tint_color[1], tint_color[2])
        tint_lut = _build_tint_lut_bytes(int(tint_color) & 0xFFFF)
    for row in range(start_row, end_row):
        fb_y = dy + row
        src_y = sy + row
        src_offset = 4 + src_y * src_row_bytes + src_x * bytes_per_pixel
        fh.seek(src_offset)
        fh.readinto(linebuf)
        if tint_lut is not None and bytes_per_pixel == 2:
            _tint_line(linebuf, len(linebuf), tint_lut)
        framebuffer.blit((linebuf, copy_width, 1, framebuf.RGB565), fb_x, fb_y)

class BMFont:
    def __init__(self):
        self.line_height = 0
        self.base = 0
        self.scale_w = 0
        self.scale_h = 0
        self.pages = {}
        self.chars = {}  # maps codepoint -> offset into _glyph_data
        self.kerning = {}
        self._glyph_data = bytearray()

    @staticmethod
    def _dequote(s):
        if s and len(s) >= 2 and s[0] == '"' and s[-1] == '"':
            return s[1:-1]
        return s

    @staticmethod
    def _int_list(s):
        return tuple(int(v) for v in s.split(","))

    @classmethod
    def load(cls, path, load_kerning=True):
        font = cls()
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
                    # pack and store glyph data; map code -> offset
                    off = len(font._glyph_data)
                    font._glyph_data.extend(struct.pack(_GLYPH_FMT,
                        x, y, width, height, xoffset, yoffset, xadvance, page))
                    font.chars[char_id] = off
                elif kind == "kerning" and load_kerning:
                    first = int(args.get("first", 0))
                    second = int(args.get("second", 0))
                    amount = int(args.get("amount", 0))
                    font.kerning[(first, second)] = amount
        return font


def draw_text(framebuffer, display_width, display_height, font: BMFont, page_files, text, x, y, kerning=True, scale_up=1, scale_down=1, color=None):
    total_pixels = display_width * display_height
    bytes_per_pixel = len(memoryview(framebuffer)) // total_pixels
    row_bytes = font.scale_w * bytes_per_pixel
    pages = {}
    if isinstance(page_files, str):
        raise TypeError("page_files must be file objects (not paths)")
    if hasattr(page_files, 'items'):
        iterator = page_files.items()
    else:
        iterator = enumerate(page_files)
    for pid, fh in iterator:
        if not (hasattr(fh, 'seek') and hasattr(fh, 'readinto')):
            raise TypeError("page_files values must be file-like with seek and readinto")
        pages[pid] = fh
    cx = x
    cy = y
    prev_id = None
    for ch in text:
        if ch == "\n":
            cx = x
            cy += font.line_height
            prev_id = None
            continue
        code = ord(ch)
        off = font.chars.get(code)
        if off is None:
            prev_id = None
            continue
        if prev_id is not None and kerning:
            cx += font.kerning.get((prev_id, code), 0)
        src_x, src_y, width, height, xoffset, yoffset, xadvance, page = struct.unpack_from(_GLYPH_FMT, font._glyph_data, off)
        dest_x = cx + xoffset * scale_up // scale_down
        dest_y = cy + yoffset * scale_up // scale_down
        blit_region(framebuffer, display_width, display_height, bytes_per_pixel,
                    pages[page], row_bytes,
                    src_x, src_y, width, height,
                    dest_x, dest_y, color)
        cx += (xadvance * scale_up) // scale_down
        prev_id = code

def measure_text(font: BMFont, text: str, kerning=True):
    max_width = 0
    lines = 1 if text != "" else 0
    cx = 0
    prev_id = None
    min_x = None
    max_x = None
    for ch in text:
        if ch == "\n":
            if min_x is not None:
                w = max_x - min_x
                if w > max_width:
                    max_width = w
            lines += 1
            cx = 0
            prev_id = None
            min_x = None
            max_x = None
            continue
        code = ord(ch)
        off = font.chars.get(code)
        if off is None:
            prev_id = None
            continue
        if prev_id is not None and kerning:
            cx += font.kerning.get((prev_id, code), 0)
        _, _, width, _, xoffset, _, xadvance, _ = struct.unpack_from(_GLYPH_FMT, font._glyph_data, off)
        glyph_left = cx + xoffset
        glyph_right = glyph_left + width
        if min_x is None or glyph_left < min_x:
            min_x = glyph_left
        if max_x is None or glyph_right > max_x:
            max_x = glyph_right
        cx += xadvance
        prev_id = code
    if min_x is not None:
        w = max_x - min_x
        if w > max_width:
            max_width = w
    height = lines * font.line_height
    return max_width, height
