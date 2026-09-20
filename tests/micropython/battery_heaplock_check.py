import gc
import micropython

from drawing import Drawing
import battery
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


d565 = Drawing(WIDTH, HEIGHT, 'RGB565')
d332 = Drawing(WIDTH, HEIGHT, 'GS8')


def draw_right_565():
    battery.draw_battery(d565, (10, 10), (120, 60), 63)


def draw_right_332():
    battery.draw_battery(d332, (10, 10), (120, 60), 63)


def draw_up_565():
    battery.draw_battery(d565, (10, 10), (60, 140), 30, orientation='up')


def draw_none_565():
    battery.draw_battery(d565, (10, 10), (120, 60), None)


draw_right_565()
draw_right_332()
draw_up_565()
draw_none_565()


def main():
    res, _ = under_lock(lambda: bytearray(1))
    check('heap_lock forbids allocation', res == 'raised',
          'bytearray(1) under lock did not raise')

    for label, fn in [('draw_battery right rgb565 under heap_lock', draw_right_565),
                      ('draw_battery right gs8 under heap_lock', draw_right_332),
                      ('draw_battery up rgb565 under heap_lock', draw_up_565),
                      ('draw_battery none rgb565 under heap_lock', draw_none_565)]:
        res, delta = under_lock(fn)
        check(label, res == 'ok' and delta == 0,
              'res=%s delta=%d' % (res, delta))

    summarize()

main()
