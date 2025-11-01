import struct
import gc
from bitblt import blit_region

# Glyphs are stored compactly in a bytearray to minimize RAM.
# Packed layout (little-endian): x,y,width,height (uint16), xoffset,yoffset,xadvance (int16), page (uint8)
_GLYPH_FMT = '<HHHHhhhB'

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


def draw_text(framebuffer, display_width, display_height, font: BMFont, page_files, text, x, y, kerning=True, scale_up=1, scale_down=1):
    total_pixels = display_width * display_height
    bytes_per_pixel = len(framebuffer) // total_pixels
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
                    pages[page], 4, row_bytes,
                    src_x, src_y, width, height,
                    dest_x, dest_y)
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
