import sys

try:
    import micropython
    _IS_MICROPYTHON = sys.implementation.name == 'micropython'
except ImportError:
    _IS_MICROPYTHON = False

if not _IS_MICROPYTHON:
    class micropython:
        @staticmethod
        def viper(f): return f

    ptr8 = object

@micropython.viper
def _viper_skip_whitespace(buf: ptr8, pos: int, end: int) -> int:
    i = pos
    while i < end:
        c = buf[i]
        if c != 32 and c != 9 and c != 10 and c != 13:
            break
        i += 1
    return i

@micropython.viper
def _viper_skip_number_chars(buf: ptr8, pos: int, end: int) -> int:
    i = pos
    while i < end:
        c = buf[i]
        if not ((c >= 48 and c <= 57) or c == 45 or c == 43 or c == 46 or c == 101 or c == 69):
            break
        i += 1
    return i

def _unescape_string(s):
    if '\\' not in s:
        return s
    
    res = bytearray()
    i = 0
    length = len(s)
    while i < length:
        c = s[i]
        if c == '\\':
            i += 1
            if i >= length: break
            esc = s[i]
            if esc == '"': res.append(0x22)
            elif esc == '\\': res.append(0x5c)
            elif esc == '/': res.append(0x2f)
            elif esc == 'b': res.append(0x08)
            elif esc == 'f': res.append(0x0c)
            elif esc == 'n': res.append(0x0a)
            elif esc == 'r': res.append(0x0d)
            elif esc == 't': res.append(0x09)
            elif esc == 'u':
                if i + 4 < length:
                    hex_str = s[i+1:i+5]
                    try:
                        res.extend(chr(int(hex_str, 16)).encode('utf-8'))
                    except ValueError:
                        pass
                    i += 4
            else:
                res.append(0x5c)
                res.extend(esc.encode('utf-8'))
        else:
            res.extend(c.encode('utf-8'))
        i += 1
    return res.decode('utf-8')

async def _read_all(source, chunk_size=256):
    chunks = []
    if hasattr(source, 'read'):
        while True:
            chunk = await source.read(chunk_size)
            if not chunk:
                break
            chunks.append(chunk)
    else:
        iterable = source.__aiter__() if hasattr(source, '__aiter__') else source
        while True:
            try:
                chunk = await iterable.__anext__()
            except StopAsyncIteration:
                break
            if chunk is not None:
                chunks.append(chunk)
    return b''.join(chunks)


class _SyncJsonParser:
    def __init__(self, buf, ignore_keys=None):
        self.buf = buf
        self.pos = 0
        self.end = len(buf)
        if not ignore_keys:
            self.ignore_keys = ()
        elif isinstance(ignore_keys, (set, frozenset)):
            self.ignore_keys = ignore_keys
        else:
            self.ignore_keys = set(ignore_keys)

    def skip_whitespace(self):
        self.pos = _viper_skip_whitespace(self.buf, self.pos, self.end)

    def parse_value(self):
        self.skip_whitespace()
        if self.pos >= self.end:
            return None

        c = self.buf[self.pos]
        if c == ord('{'): return self.parse_object()
        elif c == ord('['): return self.parse_array()
        elif c == ord('"'): return self.parse_string()
        elif c == ord('t'):
            if self.pos + 4 > self.end or self.buf[self.pos:self.pos + 4] != b'true':
                raise ValueError(f"Invalid literal at position {self.pos}")
            self.pos += 4
            return True
        elif c == ord('f'):
            if self.pos + 5 > self.end or self.buf[self.pos:self.pos + 5] != b'false':
                raise ValueError(f"Invalid literal at position {self.pos}")
            self.pos += 5
            return False
        elif c == ord('n'):
            if self.pos + 4 > self.end or self.buf[self.pos:self.pos + 4] != b'null':
                raise ValueError(f"Invalid literal at position {self.pos}")
            self.pos += 4
            return None
        elif c in b']}:,':
            raise ValueError(f"Unexpected character '{chr(c)}' at position {self.pos}")
        elif c in b'-+0123456789':
            return self.parse_number()
        else:
            raise ValueError(f"Unexpected character '{chr(c)}' at position {self.pos}")

    def parse_number(self):
        start = self.pos
        self.pos = _viper_skip_number_chars(self.buf, self.pos, self.end)
        val = self.buf[start:self.pos]
        if not val or val in (b'-', b'+'):
            raise ValueError(f"Expected number but got empty string near position {start}")
        if b'.' in val or b'e' in val or b'E' in val:
            return float(val)
        return int(val)

    def _find_close_quote(self, pos):
        buf = self.buf
        end = self.end
        while True:
            quote_pos = buf.find(b'"', pos, end)
            if quote_pos == -1:
                raise ValueError("Unterminated string")
            backslash_pos = buf.find(b'\\', pos, quote_pos)
            if backslash_pos == -1:
                return quote_pos
            pos = backslash_pos + 2

    def parse_string(self):
        self.pos += 1
        start = self.pos
        quote_pos = self._find_close_quote(start)
        segment = self.buf[start:quote_pos].decode('utf-8')
        self.pos = quote_pos + 1
        return _unescape_string(segment)

    def skip_string(self):
        self.pos += 1
        self.pos = self._find_close_quote(self.pos) + 1

    def skip_container(self, open_byte, close_byte):
        open_needle = bytes((open_byte,))
        close_needle = bytes((close_byte,))
        depth = 1
        self.pos += 1
        buf = self.buf
        end = self.end
        while depth > 0:
            open_pos = buf.find(open_needle, self.pos, end)
            close_pos = buf.find(close_needle, self.pos, end)
            quote_pos = buf.find(b'"', self.pos, end)

            nearest = end
            if open_pos != -1 and open_pos < nearest:
                nearest = open_pos
            if close_pos != -1 and close_pos < nearest:
                nearest = close_pos
            if quote_pos != -1 and quote_pos < nearest:
                nearest = quote_pos

            self.pos = nearest
            if self.pos >= end:
                return

            c = buf[self.pos]
            if c == 0x22:
                self.skip_string()
                continue

            self.pos += 1
            if c == open_byte:
                depth += 1
            else:
                depth -= 1
                if depth == 0:
                    return

    def fast_skip_value(self):
        self.skip_whitespace()
        if self.pos >= self.end:
            return

        c = self.buf[self.pos]
        if c == ord('{'):
            self.skip_container(ord('{'), ord('}'))
        elif c == ord('['):
            self.skip_container(ord('['), ord(']'))
        elif c == ord('"'):
            self.skip_string()
        elif c == ord('t'):
            if self.pos + 4 > self.end or self.buf[self.pos:self.pos + 4] != b'true':
                raise ValueError(f"Invalid literal at position {self.pos}")
            self.pos += 4
        elif c == ord('f'):
            if self.pos + 5 > self.end or self.buf[self.pos:self.pos + 5] != b'false':
                raise ValueError(f"Invalid literal at position {self.pos}")
            self.pos += 5
        elif c == ord('n'):
            if self.pos + 4 > self.end or self.buf[self.pos:self.pos + 4] != b'null':
                raise ValueError(f"Invalid literal at position {self.pos}")
            self.pos += 4
        else:
            self.pos = _viper_skip_number_chars(self.buf, self.pos, self.end)

    def parse_object(self):
        self.pos += 1
        self.skip_whitespace()

        obj = {}
        if self.pos < self.end and self.buf[self.pos] == ord('}'):
            self.pos += 1
            return obj

        while True:
            self.skip_whitespace()
            if self.pos >= self.end or self.buf[self.pos] == ord('}'):
                break

            key = None
            if self.buf[self.pos] == ord('"'):
                key = self.parse_string()

            self.skip_whitespace()
            if self.pos < self.end and self.buf[self.pos] == ord(':'):
                self.pos += 1

            if key in self.ignore_keys:
                self.fast_skip_value()
            else:
                val = self.parse_value()
                if key is not None:
                    obj[key] = val

            self.skip_whitespace()
            if self.pos < self.end and self.buf[self.pos] == ord('}'):
                self.pos += 1
                break
            if self.pos < self.end and self.buf[self.pos] == ord(','):
                self.pos += 1
        return obj

    def parse_array(self):
        self.pos += 1
        self.skip_whitespace()

        arr = []
        if self.pos < self.end and self.buf[self.pos] == ord(']'):
            self.pos += 1
            return arr

        while True:
            arr.append(self.parse_value())

            self.skip_whitespace()
            if self.pos < self.end and self.buf[self.pos] == ord(']'):
                self.pos += 1
                break
            if self.pos < self.end and self.buf[self.pos] == ord(','):
                self.pos += 1
        return arr


def loads(data, ignore_keys=None):
    return _SyncJsonParser(data, ignore_keys).parse_value()

async def load(async_iterable, ignore_keys=None):
    data = await _read_all(async_iterable)
    return loads(data, ignore_keys)

class _AsyncListIterator:
    def __init__(self, async_iterable):
        self.source = async_iterable
        self.iterable = None
        self.buf = bytearray()
        self.pos = 0
        self.exhausted = False
        self.started = False
        self.finished = False

    def __aiter__(self):
        return self

    async def _fetch(self):
        if self.exhausted:
            return False
        if hasattr(self.source, 'read'):
            chunk = await self.source.read(256)
        else:
            if self.iterable is None:
                self.iterable = self.source.__aiter__() if hasattr(self.source, '__aiter__') else self.source
            try:
                chunk = await self.iterable.__anext__()
            except StopAsyncIteration:
                chunk = None
        if not chunk:
            self.exhausted = True
            return False
        self.buf.extend(chunk)
        return True

    def _drop_consumed(self):
        if self.pos > 0:
            self.buf = self.buf[self.pos:]
            self.pos = 0

    async def _skip_whitespace_incremental(self):
        while True:
            self._drop_consumed()
            self.pos = _viper_skip_whitespace(self.buf, self.pos, len(self.buf))
            if self.pos < len(self.buf):
                return True
            if not await self._fetch():
                return False

    async def _parse_value_incremental(self):
        while True:
            parser = _SyncJsonParser(self.buf)
            parser.pos = self.pos
            try:
                val = parser.parse_value()
            except (IndexError, ValueError):
                if not await self._fetch():
                    raise
                continue
            if isinstance(val, (int, float)) and parser.pos == len(self.buf):
                if await self._fetch():
                    continue
            self.pos = parser.pos
            return val

    async def __anext__(self):
        if self.finished:
            raise StopAsyncIteration

        if not self.started:
            if not await self._skip_whitespace_incremental():
                self.finished = True
                raise StopAsyncIteration
            if self.buf[self.pos] != ord('['):
                self.finished = True
                raise ValueError("Expected '[' at start of array")
            self.pos += 1
            self.started = True

        if not await self._skip_whitespace_incremental():
            self.finished = True
            raise StopAsyncIteration

        if self.buf[self.pos] == ord(']'):
            self.pos += 1
            self.finished = True
            raise StopAsyncIteration

        val = await self._parse_value_incremental()

        if await self._skip_whitespace_incremental():
            c = self.buf[self.pos]
            if c == ord(']'):
                self.pos += 1
                self.finished = True
            elif c == ord(','):
                self.pos += 1
        else:
            self.finished = True

        return val

def load_array(async_iterable):
    return _AsyncListIterator(async_iterable)
