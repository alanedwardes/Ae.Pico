import gc
import micropython

from bmfont import BMFont, draw_text, measure_text
from mpassets import load_bytes, stage
from microcheck import check, summarize

FONT_PATH = 'cpython/fonts/regular.fnt'
ATLAS_PATH = 'cpython/fonts/regular_0.bin'

FB_WIDTH = 320
FB_HEIGHT = 64
TEXT = 'The quick brown fox jumps over the lazy dog!'
SHORT = '13:37'


class FB:
    def __init__(self, width, height, bytes_per_pixel):
        self.width = width
        self.height = height
        self.bytes_per_pixel = bytes_per_pixel
        self._buf = bytearray(width * height * bytes_per_pixel)


def under_lock(fn):
    gc.collect()
    before = gc.mem_alloc()
    try:
        micropython.heap_lock()
        fn()
        micropython.heap_unlock()
    except MemoryError:
        micropython.heap_unlock()
        return ('raised', None)
    return ('ok', gc.mem_alloc() - before)


def production_lock_ok(fn):
    gc.collect()
    try:
        fn()
    except MemoryError:
        return False
    return True


font = BMFont.load(stage(FONT_PATH))
atlas = load_bytes(ATLAS_PATH)
pages = {0: atlas}

fb565 = FB(FB_WIDTH, FB_HEIGHT, 2)
fb332 = FB(FB_WIDTH, FB_HEIGHT, 1)
linebuf = memoryview(bytearray(font.scale_w * 8))
clip_box = (0, 0, FB_WIDTH, FB_HEIGHT)


def draw_565():
    draw_text(fb565, FB_WIDTH, FB_HEIGHT, font, pages, TEXT, 2, 2,
              linebuf=linebuf)


def draw_565_background():
    draw_text(fb565, FB_WIDTH, FB_HEIGHT, font, pages, TEXT, 2, 2,
              linebuf=linebuf, color=0xFFFFFF, background=0x000000, clip=clip_box)


def draw_565_short_background():
    draw_text(fb565, FB_WIDTH, FB_HEIGHT, font, pages, SHORT, 2, 2,
              linebuf=linebuf, color=0xFFFFFF, background=0x000000, clip=clip_box)


def draw_332():
    draw_text(fb332, FB_WIDTH, FB_HEIGHT, font, pages, TEXT, 2, 2,
              linebuf=linebuf)


def draw_332_background():
    draw_text(fb332, FB_WIDTH, FB_HEIGHT, font, pages, TEXT, 2, 2,
              linebuf=linebuf, color=0xFFFFFF, background=0x000000, clip=clip_box)


MULTILINE = 'The quick\nbrown fox\njumps'

def measure_normal():
    measure_text(font, TEXT)


def measure_multiline():
    measure_text(font, MULTILINE)


def measure_empty():
    measure_text(font, '')


warm = [
    ('draw_text rgb565', draw_565),
    ('draw_text rgb565 background', draw_565_background),
    ('draw_text rgb565 short background', draw_565_short_background),
    ('draw_text rgb332', draw_332),
    ('draw_text rgb332 background', draw_332_background),
]

measure = [
    ('measure_text normal', measure_normal),
    ('measure_text multiline', measure_multiline),
    ('measure_text empty', measure_empty),
]

for _, fn in warm:
    fn()
for _, fn in measure:
    fn()


def main():
    res, _ = under_lock(lambda: bytearray(1))
    check('heap_lock forbids allocation', res == 'raised',
          'bytearray(1) under lock did not raise')

    for label, fn in warm:
        res, delta = under_lock(fn)
        check('%s under heap_lock' % label, res == 'ok' and delta == 0,
              'res=%s delta=%d' % (res, delta))

    for label, fn in measure:
        check('%s under production lock' % label, production_lock_ok(fn),
              'raised MemoryError under production lock')

    summarize()

main()