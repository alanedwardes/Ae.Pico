import gc
import micropython

from mipidcs import (
    _rgb565_to_888_line,
    _rgb565_swap_line,
    _rgb332_to_888_line,
    _rgb332_to_565_line,
    build_rgb332_888_lut,
)
from microcheck import check, summarize

PIXELS = 320


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


src565 = bytearray(PIXELS * 2)
src332 = bytearray(PIXELS)
dst888 = bytearray(PIXELS * 3)
dst565 = bytearray(PIXELS * 2)
lut565 = bytearray(128)
lut332_888 = build_rgb332_888_lut()
lut332_565 = bytearray(512)


def conv_565_to_888():
    _rgb565_to_888_line(dst888, src565, 0, PIXELS, lut565)


def conv_565_swap():
    _rgb565_swap_line(dst565, src565, 0, PIXELS, lut565)


def conv_332_to_888():
    _rgb332_to_888_line(dst888, src332, 0, PIXELS, lut332_888)


def conv_332_to_565():
    _rgb332_to_565_line(dst565, src332, 0, PIXELS, lut332_565)


warm = [
    ('rgb565 -> rgb888', conv_565_to_888),
    ('rgb565 swap', conv_565_swap),
    ('rgb332 -> rgb888', conv_332_to_888),
    ('rgb332 -> rgb565', conv_332_to_565),
]

for _, fn in warm:
    fn()


def main():
    res, _ = under_lock(lambda: bytearray(1))
    check('heap_lock forbids allocation', res == 'raised',
          'bytearray(1) under lock did not raise')

    for label, fn in warm:
        res, delta = under_lock(fn)
        check('%s under heap_lock' % label, res == 'ok' and delta == 0,
              'res=%s delta=%d' % (res, delta))

    summarize()

main()