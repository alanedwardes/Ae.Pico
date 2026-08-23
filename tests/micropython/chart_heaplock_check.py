import asyncio
import binascii
import gc
import micropython

from drawing import Drawing
import chart
from chart import _as_ptr8, _as_ptr16
from microcheck import check, summarize

WIDTH = 320
HEIGHT = 120
VALUES = [0.0, 0.1, 0.45, 0.3, 0.8, 1.0, 0.65, 0.2, 0.5, 0.9, 0.35, 0.0]
RAW = [v * 10 for v in VALUES]
Q8 = [int(v * 256) for v in VALUES]

EXPECTED_CRC = 0xea79d576


def color_fn(index, value):
    if value > 7:
        return 0xFF3B30
    if value > 4:
        return 0xFFCC00
    return 0x34C759


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


chart._compute_curve(10, WIDTH - 20, HEIGHT - 20, Q8, 256)
COLS = chart._cols_cache
YFP = chart._yfp_cache
N = len(Q8)
NCOLS = (WIDTH - 20) + 1

FB = bytearray(WIDTH * HEIGHT * 2)
D8 = _as_ptr8(FB)
D16 = _as_ptr16(FB)
P = chart._render_params
P[0] = 0; P[1] = WIDTH - 20
P[2] = 10; P[3] = HEIGHT; P[4] = HEIGHT
P[5] = 1; P[6] = 256; P[7] = 1
P[8] = 2; P[9] = WIDTH; P[10] = WIDTH * 2
P[11] = 0xFF; P[12] = 0x3B; P[13] = 0x30
P[14] = 0x7F; P[15] = 0x1D; P[16] = 0x18
P[17] = 0xFD3B; P[18] = 0x7B1D


def compute_curve_warm():
    chart._compute_curve(10, WIDTH - 20, HEIGHT - 20, Q8, 256)


def curve_kernel():
    chart._curve_cols_viper(YFP, N, COLS, NCOLS, 10, 256)


def render_kernel():
    chart._render_cols_viper(D8, D16, COLS, P)


def regular_def_call():
    def f():
        return 1 + 1
    return f()


def main():
    res, _ = alloc_under_lock(lambda: bytearray(1))
    check('heap_lock forbids allocation', res == 'raised',
          'bytearray(1) under lock did not raise')

    res, _ = alloc_under_lock(regular_def_call)
    check('def call allocates (lock excludes python calls)', res == 'raised',
          'regular def call did not raise under lock')

    res, delta = alloc_under_lock(compute_curve_warm)
    check('_compute_curve under heap_lock', res == 'ok' and delta == 0,
          'res=%s delta=%d' % (res, delta))

    res, delta = alloc_under_lock(curve_kernel)
    check('curve kernel under heap_lock', res == 'ok' and delta == 0,
          'res=%s delta=%d' % (res, delta))

    res, delta = alloc_under_lock(render_kernel)
    check('render kernel under heap_lock', res == 'ok' and delta == 0,
          'res=%s delta=%d' % (res, delta))

    display = Drawing(WIDTH, HEIGHT, 'RGB565')
    try:
        asyncio.run(chart.draw_segmented_area(
            display, 10, 10, 300, 100, RAW, Q8, color_fn))
    except MemoryError as e:
        check('draw_segmented_area under production lock', False,
              'raised MemoryError: %s' % e)
        summarize()
        return
    crc = binascii.crc32(display._framebuffer)
    check('draw_segmented_area completes', True)
    check('draw_segmented_area pixels unchanged by lock',
          crc == EXPECTED_CRC, 'crc 0x%08x != 0x%08x' % (crc, EXPECTED_CRC))

    summarize()

main()