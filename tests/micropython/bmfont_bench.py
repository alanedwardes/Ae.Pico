import struct
from io import BytesIO

from bmfont import BMFont, draw_text, measure_text
from bitblt import blit_region
from drawing import Drawing
from microbench import bench, compare
from mpassets import load_bytes, stage

FONT_PATH = 'cpython/fonts/regular.fnt'
ATLAS_PATH = 'cpython/fonts/regular_0.bin'
HEADLINE_FONT_PATH = 'cpython/fonts/headline.fnt'
HEADLINE_ATLAS_PATH = 'cpython/fonts/headline_0.bin'
ICON_W = 24
ICON_H = 24

FB_WIDTH = 320
FB_HEIGHT = 480

TEXT = 'The quick brown fox jumps over the lazy dog!'

class FB:
    def __init__(self, width, height, bytes_per_pixel):
        self.width = width
        self.height = height
        self.bytes_per_pixel = bytes_per_pixel
        self._buf = bytearray(width * height * bytes_per_pixel)

def main():
    font = BMFont.load(stage(FONT_PATH))
    atlas = load_bytes(ATLAS_PATH)
    icon = BytesIO(struct.pack('<HH', ICON_W, ICON_H) + bytes(ICON_W * ICON_H))

    fb565 = FB(FB_WIDTH, FB_HEIGHT, 2)
    fb332 = FB(FB_WIDTH, FB_HEIGHT, 1)
    pages = {0: atlas}

    linebuf_1 = memoryview(bytearray(font.scale_w))
    linebuf_8 = memoryview(bytearray(font.scale_w * 8))

    bench('draw_text rgb565 no linebuf',
          lambda: draw_text(fb565, FB_WIDTH, FB_HEIGHT, font, pages, TEXT, 10, 10))
    bench('draw_text rgb565 1-row linebuf',
          lambda: draw_text(fb565, FB_WIDTH, FB_HEIGHT, font, pages, TEXT, 10, 10, linebuf=linebuf_1))
    bench('draw_text rgb565 8-row linebuf',
          lambda: draw_text(fb565, FB_WIDTH, FB_HEIGHT, font, pages, TEXT, 10, 10, linebuf=linebuf_8))
    bench('draw_text rgb565 tinted',
          lambda: draw_text(fb565, FB_WIDTH, FB_HEIGHT, font, pages, TEXT, 10, 10, linebuf=linebuf_8, color=0xFF8800))
    bench('draw_text rgb565 clipped',
          lambda: draw_text(fb565, FB_WIDTH, FB_HEIGHT, font, pages, TEXT, 10, 10, linebuf=linebuf_8, clip=(0, 0, 160, 30)))
    bench('draw_text rgb332 8-row linebuf',
          lambda: draw_text(fb332, FB_WIDTH, FB_HEIGHT, font, pages, TEXT, 10, 10, linebuf=linebuf_8))
    bench('measure_text',
          lambda: measure_text(font, TEXT.encode()))

    icon_buf = memoryview(bytearray(ICON_W * 8))
    bench('blit_region icon gs8->rgb565 direct',
          lambda: blit_region(fb565, FB_WIDTH, FB_HEIGHT, 2, icon, 4, ICON_W,
                              0, 0, ICON_W, ICON_H, 50, 50, buffer=icon_buf, src_format=6))

    headline = BMFont.load(stage(HEADLINE_FONT_PATH))
    headline_atlas = load_bytes(HEADLINE_ATLAS_PATH)
    headline_pages = {0: headline_atlas}
    d = Drawing(320, 480, 'RGB565')
    d_linebuf = d.get_scratch_buffer(headline.scale_w)
    clip_box = (0, 0, 260, 90)

    def old_style(text, font_obj, pages_obj, linebuf_obj):
        d.rect(clip_box[0], clip_box[1], clip_box[2], clip_box[3], 0x000000, True)
        draw_text(d, 320, 480, font_obj, pages_obj, text, 10, 10,
                  linebuf=linebuf_obj, color=0xFFFFFF, clip=clip_box)

    def new_style(text, font_obj, pages_obj, linebuf_obj):
        draw_text(d, 320, 480, font_obj, pages_obj, text, 10, 10,
                  linebuf=linebuf_obj, color=0xFFFFFF, background=0x000000, clip=clip_box)

    bench('old-style (rect+masked blit) "13:37" headline',
          lambda: old_style('13:37', headline, headline_pages, d_linebuf))
    bench('new-style (composite) "13:37" headline',
          lambda: new_style('13:37', headline, headline_pages, d_linebuf))
    compare('old-style "13:37"', lambda: old_style('13:37', headline, headline_pages, d_linebuf),
            'new-style "13:37"', lambda: new_style('13:37', headline, headline_pages, d_linebuf))

    d_linebuf_regular = d.get_scratch_buffer(font.scale_w)
    bench('old-style (rect+masked blit) long text regular',
          lambda: old_style(TEXT, font, pages, d_linebuf_regular))
    bench('new-style (composite) long text regular',
          lambda: new_style(TEXT, font, pages, d_linebuf_regular))
    compare('old-style long text', lambda: old_style(TEXT, font, pages, d_linebuf_regular),
            'new-style long text', lambda: new_style(TEXT, font, pages, d_linebuf_regular))

    d332 = Drawing(320, 480, 'RGB332')
    d332_linebuf_regular = d332.get_scratch_buffer(font.scale_w)

    def old_style332(text, font_obj, pages_obj, linebuf_obj):
        d332.rect(clip_box[0], clip_box[1], clip_box[2], clip_box[3], 0x000000, True)
        draw_text(d332, 320, 480, font_obj, pages_obj, text, 10, 10,
                  linebuf=linebuf_obj, color=0xFFFFFF, clip=clip_box)

    def new_style332(text, font_obj, pages_obj, linebuf_obj):
        draw_text(d332, 320, 480, font_obj, pages_obj, text, 10, 10,
                  linebuf=linebuf_obj, color=0xFFFFFF, background=0x000000, clip=clip_box)

    bench('old-style (rect+masked blit) long text regular rgb332',
          lambda: old_style332(TEXT, font, pages, d332_linebuf_regular))
    bench('new-style (composite) long text regular rgb332',
          lambda: new_style332(TEXT, font, pages, d332_linebuf_regular))
    compare('old-style long text rgb332', lambda: old_style332(TEXT, font, pages, d332_linebuf_regular),
            'new-style long text rgb332', lambda: new_style332(TEXT, font, pages, d332_linebuf_regular))

main()