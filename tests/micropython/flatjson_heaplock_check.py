import gc
import micropython

from flatjson import _SyncJsonParser, _viper_skip_whitespace, _viper_skip_number_chars
from microcheck import check, summarize


def alloc_under_lock(fn):
    gc.collect()
    try:
        micropython.heap_lock()
        fn()
        micropython.heap_unlock()
    except MemoryError:
        micropython.heap_unlock()
        return 'raised'
    return 'ok'


def main():
    buf = bytearray(b'   {"a":"bcdefghijklmnop","n":12345,"x":"y\\"z"}   ')
    numbuf = bytearray(b'12345')

    warm = _SyncJsonParser(bytearray(buf))
    warm.parse_value()
    int(numbuf)
    buf.find(b'"', 0, len(buf))
    _viper_skip_whitespace(buf, 0, len(buf))
    _viper_skip_number_chars(numbuf, 0, len(numbuf))

    p = _SyncJsonParser(buf)
    p.pos = 0
    res = alloc_under_lock(lambda: p.skip_whitespace())
    check('skip_whitespace() does not allocate once warmed up', res == 'ok', 'res=%s' % res)

    res = alloc_under_lock(lambda: int(numbuf))
    check('int(bytearray) does not allocate', res == 'ok', 'res=%s' % res)

    res = alloc_under_lock(lambda: float(numbuf))
    check('float(bytearray) always allocates (no tagged-float representation)', res == 'raised', 'res=%s' % res)

    res = alloc_under_lock(lambda: buf.find(b'"', 0, len(buf)))
    check('bytearray.find() does not allocate', res == 'ok', 'res=%s' % res)

    res = alloc_under_lock(lambda: _viper_skip_whitespace(buf, 0, len(buf)))
    check('_viper_skip_whitespace() does not allocate', res == 'ok', 'res=%s' % res)

    res = alloc_under_lock(lambda: _viper_skip_number_chars(numbuf, 0, len(numbuf)))
    check('_viper_skip_number_chars() does not allocate', res == 'ok', 'res=%s' % res)

    p2 = _SyncJsonParser(bytearray(b'{"a":"bcdefghijklmnop","n":12345,"x":"y\\"z"}'))
    result = p2.parse_value()
    check('full sync parse produces the correct result',
          result == {"a": "bcdefghijklmnop", "n": 12345, "x": 'y"z'}, 'result=%r' % (result,))

    summarize()

main()
