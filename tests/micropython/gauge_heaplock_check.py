import gc
import micropython

from drawing import Drawing
import gauge
from microcheck import check, summarize

WIDTH = 160
HEIGHT = 160


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


d565 = Drawing(WIDTH, HEIGHT, 'RGB565')
d332 = Drawing(WIDTH, HEIGHT, 'GS8')


def draw_norange_565():
    gauge.draw_gauge(d565, (10, 10), (140, 140))


def draw_norange_332():
    gauge.draw_gauge(d332, (10, 10), (140, 140))


def draw_range_565():
    gauge.draw_gauge(d565, (10, 10), (140, 140), 15.0, 25.0, 21.5, 18.0)


def draw_range_332():
    gauge.draw_gauge(d332, (10, 10), (140, 140), 15.0, 25.0, 21.5, 18.0)


draw_norange_565()
draw_norange_332()
draw_range_565()
draw_range_332()


def main():
    res, _ = under_lock(lambda: bytearray(1))
    check('heap_lock forbids allocation', res == 'raised',
          'bytearray(1) under lock did not raise')

    for label, fn in [('draw_gauge no-range rgb565 under heap_lock', draw_norange_565),
                      ('draw_gauge no-range gs8 under heap_lock', draw_norange_332)]:
        res, delta = under_lock(fn)
        check(label, res == 'ok' and delta == 0,
              'res=%s delta=%d' % (res, delta))

    for label, fn in [('draw_gauge range+sec rgb565 under production lock', draw_range_565),
                      ('draw_gauge range+sec gs8 under production lock', draw_range_332)]:
        check(label, production_lock_ok(fn),
              'raised MemoryError under production lock')

    summarize()

main()