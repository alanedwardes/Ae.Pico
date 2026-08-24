import asyncio
import gc

from bmfont import BMFont
import mpassets
from drawing import Drawing
import textbox
from microbench import compare

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

    def cmp(label, text, x, y, w, h, *, font, scale, wrap=False, collect=False):
        def make(bg):
            def fn():
                if collect: gc.collect()
                asyncio.run(textbox.draw_textbox(
                    display, text, x, y, w, h, color=0xFFFFFF, font=font,
                    scale=scale, wrap=wrap, background=bg))
            return fn
        compare(label + ' (transparent)', make(None), label + ' (background)', make(0x000000))

    cmp('1 digit (small)', '7', 250, 35, 36, 35, font='small', scale=1.0)
    cmp('2 digits (regular)', '42', 200, 35, 36, 35, font='regular', scale=1.0)
    cmp('HH:MM (headline)', '13:37', 0, 5, 200, 65, font='headline', scale=1.0)
    cmp('clock number (small)', '12', 100, 100, 30, 30, font='small', scale=1.0)
    cmp('wrapped news (regular)', NEWS, 0, 70, WIDTH, HEIGHT - 70,
        font='regular', scale=1.0, wrap=True, collect=True)

main()