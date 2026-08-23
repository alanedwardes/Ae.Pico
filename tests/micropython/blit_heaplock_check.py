import gc
import struct
import micropython
from io import BytesIO

from bitblt import blit_region, composite_region, fill_region
from microcheck import check, summarize

FB_WIDTH = 320
FB_HEIGHT = 480
ICON_W = 24
ICON_H = 24
CELL_H = ICON_H + 4
GLYPH_Y = 2
DX = 50
DY = 50


class FB:
    def __init__(self, width, height, bytes_per_pixel):
        self.width = width
        self.height = height
        self.bytes_per_pixel = bytes_per_pixel
        self._buf = bytearray(width * height * bytes_per_pixel)


gs8_src = BytesIO(struct.pack('<HH', ICON_W, ICON_H) + bytes(ICON_W * ICON_H))
rgb565_src = BytesIO(struct.pack('<HH', ICON_W, ICON_H) + bytes(ICON_W * ICON_H * 2))
palette565 = bytearray(512)
palette332 = bytearray(256)
fb565 = FB(FB_WIDTH, FB_HEIGHT, 2)
fb332 = FB(FB_WIDTH, FB_HEIGHT, 1)
warm_buffer = memoryview(bytearray(ICON_W * 2 * 8))
cold_buffer = bytearray(ICON_W * 2 * 8)


def alloc_under_lock(fn):
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


def blit_gs8_palette565():
    blit_region(fb565, FB_WIDTH, FB_HEIGHT, 2, gs8_src, 4, ICON_W,
                0, 0, ICON_W, ICON_H, DX, DY, warm_buffer, 6, palette565, None, -1)


def blit_gs8_direct565():
    blit_region(fb565, FB_WIDTH, FB_HEIGHT, 2, gs8_src, 4, ICON_W,
                0, 0, ICON_W, ICON_H, DX, DY, warm_buffer, 6, None, None, -1)


def blit_rgb565_to565():
    blit_region(fb565, FB_WIDTH, FB_HEIGHT, 2, rgb565_src, 4, ICON_W * 2,
                0, 0, ICON_W, ICON_H, DX, DY, warm_buffer, 1, None, None, -1)


def blit_gs8_palette332():
    blit_region(fb332, FB_WIDTH, FB_HEIGHT, 1, gs8_src, 4, ICON_W,
                0, 0, ICON_W, ICON_H, DX, DY, warm_buffer, 6, palette332, None, -1)


def blit_gs8_direct332():
    blit_region(fb332, FB_WIDTH, FB_HEIGHT, 1, gs8_src, 4, ICON_W,
                0, 0, ICON_W, ICON_H, DX, DY, warm_buffer, 6, None, None, -1)


def composite565():
    composite_region(fb565, FB_WIDTH, FB_HEIGHT, 2, gs8_src, 4, ICON_W,
                     0, 0, ICON_W, ICON_H, DX, DY, ICON_W, CELL_H, 0, GLYPH_Y,
                     warm_buffer, palette565, 0x0000, None)


def composite332():
    composite_region(fb332, FB_WIDTH, FB_HEIGHT, 1, gs8_src, 4, ICON_W,
                     0, 0, ICON_W, ICON_H, DX, DY, ICON_W, CELL_H, 0, GLYPH_Y,
                     warm_buffer, palette332, 0x00, None)


def fill565():
    fill_region(fb565, FB_WIDTH, FB_HEIGHT, DX, DY, ICON_W, ICON_H, 0x0000, None)


def fill332():
    fill_region(fb332, FB_WIDTH, FB_HEIGHT, DX, DY, ICON_W, ICON_H, 0x00, None)


def blit_cold():
    blit_region(fb565, FB_WIDTH, FB_HEIGHT, 2, gs8_src, 4, ICON_W,
                0, 0, ICON_W, ICON_H, DX, DY, cold_buffer, 6, None, None, -1)


warm = [
    ('blit gs8+palette -> rgb565', blit_gs8_palette565),
    ('blit gs8 direct -> rgb565', blit_gs8_direct565),
    ('blit rgb565 -> rgb565', blit_rgb565_to565),
    ('blit gs8+palette -> rgb332', blit_gs8_palette332),
    ('blit gs8 direct -> rgb332', blit_gs8_direct332),
    ('composite gs8 -> rgb565', composite565),
    ('composite gs8 -> rgb332', composite332),
    ('fill rgb565', fill565),
    ('fill rgb332', fill332),
]

for _, fn in warm:
    fn()


def main():
    res, _ = alloc_under_lock(lambda: bytearray(1))
    check('heap_lock forbids allocation', res == 'raised',
          'bytearray(1) under lock did not raise')

    res, _ = alloc_under_lock(blit_cold)
    check('non-memoryview buffer allocates per call', res == 'raised',
          'bytearray buffer did not raise under lock')

    for label, fn in warm:
        res, delta = alloc_under_lock(fn)
        check('%s under heap_lock' % label, res == 'ok' and delta == 0,
              'res=%s delta=%d' % (res, delta))

    summarize()

main()