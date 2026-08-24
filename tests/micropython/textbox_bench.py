import asyncio

from bmfont import BMFont
import mpassets
from drawing import Drawing
import textbox
from microbench import bench

WIDTH = 320
HEIGHT = 480

NEWS = ('The quick brown fox jumps over the lazy dog while this text is '
        'wrapped, measured and rendered live by the real display stack '
        'running under MicroPython.')

def _preload_fonts(names):
    for name in names:
        textbox._BM_FONT_CACHE[name] = (
            BMFont.load(mpassets.stage('fonts/%s.fnt' % name)),
            [mpassets.load_bytes('fonts/%s_0.bin' % name)])

def main():
    import os
    if 'fonts' not in os.listdir('.'):
        os.chdir('cpython')
    _preload_fonts(('headline', 'small', 'regular'))
    display = Drawing(WIDTH, HEIGHT, 'RGB565')

    bench('textbox 1 digit (small)',
          lambda: asyncio.run(textbox.draw_textbox(
              display, '7', 250, 35, 36, 35, color=0xFFFFFF, font='small', scale=1.0)))

    bench('textbox 2 digits (regular)',
          lambda: asyncio.run(textbox.draw_textbox(
              display, '42', 200, 35, 36, 35, color=0xFFFFFF, font='regular', scale=1.0)))

    bench('textbox HH:MM (headline)',
          lambda: asyncio.run(textbox.draw_textbox(
              display, '13:37', 0, 5, 200, 65, color=0xFFFFFF, font='headline', scale=1.0)))

    bench('textbox clock number (small)',
          lambda: asyncio.run(textbox.draw_textbox(
              display, '12', 100, 100, 30, 30, color=0xFFFFFF, font='small')))

    bench('textbox wrapped news (regular)',
          lambda: asyncio.run(textbox.draw_textbox(
              display, NEWS, 0, 70, WIDTH, HEIGHT - 70,
              color=0xFFFFFF, font='regular', wrap=True)))

    font_obj = textbox._BM_FONT_CACHE['regular'][0]
    bench('word wrap news (measure only)',
          lambda: asyncio.run(textbox._word_wrap_bmfont(font_obj, NEWS, WIDTH, 1)))

main()