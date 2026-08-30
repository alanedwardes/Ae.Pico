import gc
import micropython

from flatjson import _AsyncJsonParser
from microcheck import check, summarize


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


def run_sync(coro):
    try:
        while True:
            coro.send(None)
    except StopIteration as e:
        return e.value


def alloc_delta(fn):
    gc.collect()
    before = gc.mem_alloc()
    fn()
    return gc.mem_alloc() - before


def main():
    p = _AsyncJsonParser([])
    p.buffer = bytearray(b'   {"a":"bcdefghijklmnop","n":12345,"x":"y\\"z"}   ')
    p.pos = 0

    res, _ = alloc_under_lock(lambda: run_sync(p.skip_whitespace()))
    check('calling skip_whitespace() allocates a coroutine frame',
          res == 'raised', 'res=%s' % res)
    p.pos = 3

    res, _ = alloc_under_lock(lambda: run_sync(p._fill_buffer(1)))
    check('calling _fill_buffer() allocates a coroutine frame even on its no-op path',
          res == 'raised', 'res=%s' % res)

    p.pos = 3
    just_skip_ws = alloc_delta(lambda: run_sync(p.skip_whitespace()))

    p.pos = 3
    def skip_ws_then_redundant_fill():
        run_sync(p.skip_whitespace())
        run_sync(p._fill_buffer(1))
    skip_ws_plus_redundant_call = alloc_delta(skip_ws_then_redundant_fill)

    redundant_call_cost = skip_ws_plus_redundant_call - just_skip_ws
    check('the removed redundant _fill_buffer(1) call had a real, nonzero cost',
          redundant_call_cost > 0,
          'just_skip_ws=%d combined=%d cost=%d' % (just_skip_ws, skip_ws_plus_redundant_call, redundant_call_cost))

    key_start = p.pos
    res, delta = alloc_under_lock(lambda: p.buffer.find(b'"', key_start, len(p.buffer)))
    check('bytearray.find() used by parse_string/fast_skip_string does not allocate',
          res == 'ok' and delta == 0, 'res=%s delta=%s' % (res, delta))

    res, delta = alloc_under_lock(lambda: p._needs_fill(1))
    check('_needs_fill() does not allocate', res == 'ok' and delta == 0,
          'res=%s delta=%s' % (res, delta))
    check('_needs_fill() returns False when buffer already has enough',
          p._needs_fill(1) is False, 'unexpected result')

    p2 = _AsyncJsonParser([])
    p2.buffer = bytearray(b'12345,')
    p2.pos = 0
    p2.keep_pos = 0
    def scan_number_chars():
        while p2.pos < len(p2.buffer) and p2.buffer[p2.pos] in b'-+0123456789.eE':
            p2.pos += 1
    res, delta = alloc_under_lock(scan_number_chars)
    check("parse_number's inner digit-scan loop does not allocate",
          res == 'ok' and delta == 0, 'res=%s delta=%s' % (res, delta))
    check('digit scan actually advanced pos', p2.pos == 5, 'pos=%d' % p2.pos)

    def parse_value_call():
        return p.parse_value()
    res, delta = alloc_under_lock(parse_value_call)
    check('calling an async def itself allocates a coroutine (sanity check - expected to raise)',
          res == 'raised', 'res=%s delta=%s' % (res, delta))

    summarize()

main()
