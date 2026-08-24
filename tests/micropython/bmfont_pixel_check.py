import struct

from bmfont import BMFont, draw_text
from bitblt import blit_region
from microcheck import check_pixels, summarize
from mpassets import load_bytes, stage

FONT_PATH = 'cpython/fonts/regular.fnt'
ATLAS_PATH = 'cpython/fonts/regular_0.bin'
ICON_PATH = 'cpython/icons/weather_0.bin'

FB_WIDTH = 320
FB_HEIGHT = 64

TEXT = 'The quick brown fox jumps over the lazy dog!'

EXPECTED = {
    'text rgb565': 0xfe746cf4,
    'text rgb565 tinted': 0x3c2ab12a,
    'text rgb565 clipped': 0xc6a3ee1e,
    'text rgb332': 0x380e9f78,
    'icon rgb565': 0xd574510e,
}

class FB:
    def __init__(self, width, height, bytes_per_pixel):
        self.width = width
        self.height = height
        self.bytes_per_pixel = bytes_per_pixel
        self._buf = bytearray(width * height * bytes_per_pixel)

def main():
    font = BMFont.load(stage(FONT_PATH))
    atlas = load_bytes(ATLAS_PATH)
    icon = load_bytes(ICON_PATH)
    icon_w, icon_h = struct.unpack('<HH', icon.getvalue()[:4])
    pages = {0: atlas}
    linebuf = bytearray(font.scale_w * 8)

    def scenario(label, bpp, render):
        fb = FB(FB_WIDTH, FB_HEIGHT, bpp)
        render(fb)
        check_pixels(label, fb._buf, EXPECTED.get(label))

    scenario('text rgb565', 2,
             lambda fb: draw_text(fb, FB_WIDTH, FB_HEIGHT, font, pages, TEXT, 2, 2, linebuf=linebuf))
    scenario('text rgb565 tinted', 2,
             lambda fb: draw_text(fb, FB_WIDTH, FB_HEIGHT, font, pages, TEXT, 2, 2, linebuf=linebuf, color=0xFF8800))
    scenario('text rgb565 clipped', 2,
             lambda fb: draw_text(fb, FB_WIDTH, FB_HEIGHT, font, pages, TEXT, 2, 2, linebuf=linebuf, clip=(0, 0, 160, 30)))
    scenario('text rgb332', 1,
             lambda fb: draw_text(fb, FB_WIDTH, FB_HEIGHT, font, pages, TEXT, 2, 2, linebuf=linebuf))
    scenario('icon rgb565', 2,
             lambda fb: blit_region(fb, FB_WIDTH, FB_HEIGHT, 2, icon, 4, icon_w,
                                    0, 0, icon_w, icon_h, 10, 10, src_format=6))

    summarize()

main()