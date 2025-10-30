import struct

class BMFontChar:
    def __init__(self, char_id, x, y, width, height, xoffset, yoffset, xadvance, page, chnl):
        self.char_id = char_id
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.xoffset = xoffset
        self.yoffset = yoffset
        self.xadvance = xadvance
        self.page = page
        self.chnl = chnl

class BMFont:
    def __init__(self):
        self.line_height = 0
        self.base = 0
        self.scale_w = 0
        self.scale_h = 0
        self.pages = {}
        self.chars = {}
        self.kerning = {}

    @staticmethod
    def _dequote(s):
        if s and len(s) >= 2 and s[0] == '"' and s[-1] == '"':
            return s[1:-1]
        return s

    @staticmethod
    def _int_list(s):
        return tuple(int(v) for v in s.split(","))

    @classmethod
    def load(cls, path):
        font = cls()
        with open(path, "r") as f:
            for line in f:
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
                    c = BMFontChar(
                        char_id=int(args.get("id", 0)),
                        x=int(args.get("x", 0)),
                        y=int(args.get("y", 0)),
                        width=int(args.get("width", 0)),
                        height=int(args.get("height", 0)),
                        xoffset=int(args.get("xoffset", 0)),
                        yoffset=int(args.get("yoffset", 0)),
                        xadvance=int(args.get("xadvance", 0)),
                        page=int(args.get("page", 0)),
                        chnl=int(args.get("chnl", 0)),
                    )
                    font.chars[c.char_id] = c
                elif kind == "kerning":
                    first = int(args.get("first", 0))
                    second = int(args.get("second", 0))
                    amount = int(args.get("amount", 0))
                    font.kerning[(first, second)] = amount
        return font

class _PageBin:
    def __init__(self, fh):
        self.fh = fh
        header = fh.read(4)
        self.width, self.height = struct.unpack('<HH', header)
        self.row_bytes = None

    def ensure_row_bytes(self, bytes_per_pixel):
        if self.row_bytes is None:
            self.row_bytes = self.width * bytes_per_pixel

def _blit_glyph_to_fb(framebuffer, display_width, display_height, fb_row_bytes, bpp, page: _PageBin, sx, sy, sw, sh, dx, dy):
    if sw <= 0 or sh <= 0:
        return
    if dx >= display_width or dy >= display_height:
        return
    if dx + sw <= 0 or dy + sh <= 0:
        return
    start_row = 0
    if dy < 0:
        start_row = -dy
    end_row = sh
    max_y = display_height - dy
    if end_row > max_y:
        end_row = max_y
    left_clip = 0
    if dx < 0:
        left_clip = -dx
    right_clip = 0
    over_right = dx + sw - display_width
    if over_right > 0:
        right_clip = over_right
    copy_width = sw - left_clip - right_clip
    if copy_width <= 0:
        return
    for row in range(start_row, end_row):
        fb_y = dy + row
        if fb_y < 0 or fb_y >= display_height:
            continue
        src_x = sx + left_clip
        src_y = sy + row
        fb_x = dx + left_clip
        src_offset = 4 + src_y * page.row_bytes + src_x * bpp
        fb_offset = fb_y * fb_row_bytes + fb_x * bpp
        mv = memoryview(framebuffer)[fb_offset : fb_offset + copy_width * bpp]
        page.fh.seek(src_offset)
        page.fh.readinto(mv)

def draw_text(framebuffer, display_width, display_height, font: BMFont, page_files, text, x, y, kerning=True):
    total_pixels = display_width * display_height
    bytes_per_pixel = len(framebuffer) // total_pixels
    fb_row_bytes = display_width * bytes_per_pixel
    pages = {}
    if isinstance(page_files, str):
        page_files = [page_files]
    if hasattr(page_files, 'items'):
        iterator = page_files.items()
    else:
        iterator = enumerate(page_files)
    for pid, path in iterator:
        fh = open(path, 'rb')
        pages[pid] = _PageBin(fh)
        pages[pid].ensure_row_bytes(bytes_per_pixel)
    try:
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
            c = font.chars.get(code)
            if c is None:
                prev_id = None
                continue
            if prev_id is not None and kerning:
                cx += font.kerning.get((prev_id, code), 0)
            dest_x = cx + c.xoffset
            dest_y = cy + c.yoffset
            _blit_glyph_to_fb(framebuffer, display_width, display_height, fb_row_bytes, bytes_per_pixel, pages[c.page], c.x, c.y, c.width, c.height, dest_x, dest_y)
            cx += c.xadvance
            prev_id = code
    finally:
        for p in pages.values():
            p.fh.close()

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
        c = font.chars.get(code)
        if c is None:
            prev_id = None
            continue
        if prev_id is not None and kerning:
            cx += font.kerning.get((prev_id, code), 0)
        glyph_left = cx + c.xoffset
        glyph_right = glyph_left + c.width
        if min_x is None or glyph_left < min_x:
            min_x = glyph_left
        if max_x is None or glyph_right > max_x:
            max_x = glyph_right
        cx += c.xadvance
        prev_id = code
    if min_x is not None:
        w = max_x - min_x
        if w > max_width:
            max_width = w
    height = lines * font.line_height
    return max_width, height

def _bmfont_measure_text(self, text: str, kerning=True):
    return measure_text(self, text, kerning=kerning)
