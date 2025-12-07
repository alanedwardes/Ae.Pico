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

def _build_palette565_bytes(tint_color):
    """Build a 256x1 RGB565 palette as bytes for GS8 source.

    If tint_color is None, palette maps grayscale to white (i.e., identity grayscale).
    If tint_color is RGB565 or (r,g,b), palette maps intensity to the tinted color.
    """
    if tint_color is None:
        r5 = 0x1F
        g6 = 0x3F
        b5 = 0x1F
    else:
        c = int(tint_color) & 0xFFFF
        r5 = (c >> 11) & 0x1F
        g6 = (c >> 5) & 0x3F
        b5 = c & 0x1F
    pal = bytearray(256 * 2)
    o = 0
    for i in range(256):
        tr5 = (r5 * i) // 255
        tg6 = (g6 * i) // 255
        tb5 = (b5 * i) // 255
        val = (tr5 << 11) | (tg6 << 5) | tb5
        pal[o] = val & 0xFF
        pal[o + 1] = (val >> 8) & 0xFF
        o += 2
    return pal

# Cached palette: only keep white to save memory
_WHITE_PALETTE = _build_palette565_bytes(None)

def _resolve_palette(tint_color):
    if tint_color is None:
        return _WHITE_PALETTE
    c = int(tint_color) & 0xFFFF
    if c == 0xFFFF:
        return _WHITE_PALETTE
    return _build_palette565_bytes(c)

def blit_region(framebuffer, fb_width, fb_height, fh, src_row_bytes,
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
    # GS8 source: 1 byte per pixel
    linebuf = bytearray(copy_width)
    source_framebuffer = (linebuf, copy_width, 1, framebuf.GS8)

    # Build/resolve RGB565 palette for GS8 source (white cached when tint is None/white)
    palette = _resolve_palette(tint_color)
    for row in range(start_row, end_row):
        fb_y = dy + row
        src_y = sy + row
        src_offset = 4 + src_y * src_row_bytes + src_x
        fh.seek(src_offset)
        fh.readinto(linebuf)
        # Use RGB565 palette for proper grayscale/tint across channels
        # 1-bit transparency: treat intensity 0 as transparent via key=0
        framebuffer.blit(source_framebuffer, fb_x, fb_y, 0, (palette, 256, 1, framebuf.RGB565))

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

    @staticmethod
    def _dequote(s):
        if s and len(s) >= 2 and s[0] == '"' and s[-1] == '"':
            return s[1:-1]
        return s  

    @classmethod
    def load(cls, path, load_kerning=False):
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

def draw_text(framebuffer, display_width, display_height, font: BMFont, page_files, text, x, y, kerning=False, scale_up=1, scale_down=1, color=None):
    # GS8 source atlases: one byte per pixel per row
    row_bytes = font.scale_w * 1
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
        blit_region(framebuffer, display_width, display_height,
                    pages[page], row_bytes,
                    src_x, src_y, width, height,
                    dest_x, dest_y, color)
        cx += (xadvance * scale_up) // scale_down
        prev_id = code

def measure_text(font: BMFont, text: str, kerning=False):
    """Return tight bounds of the rendered text including bearings.

    Returns (width, height, min_x, min_y) where min_x/min_y are the offsets
    from the provided origin (x, y) to the top-left of the tight bounding box.
    """
    max_right = None
    max_bottom = None
    min_left = None
    min_top = None

    cx = 0
    cy = 0
    prev_id = None

    for ch in text:
        if ch == "\n":
            cx = 0
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
        _, _, width, height, xoffset, yoffset, xadvance, _ = struct.unpack_from(_GLYPH_FMT, font._glyph_data, off)

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

    if min_left is None:
        # Empty string
        return 0, 0, 0, 0

    w = max_right - min_left
    h = max_bottom - min_top
    return w, h, min_left, min_top
