"""
Lean streaming JSON parser for flat arrays and general objects in MicroPython.
Parses elements one at a time without buffering the entire payload.
Designed for memory-constrained environments.
"""

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

class _ReaderIterable:
    """Wrapper to turn an object with a .read(n) method into an async iterator yielding chunks."""
    def __init__(self, reader, chunk_size=64):
        self.reader = reader
        self.chunk_size = chunk_size
        
    def __aiter__(self):
        return self
        
    async def __anext__(self):
        chunk = await self.reader.read(self.chunk_size)
        if not chunk:
            raise StopAsyncIteration
        return chunk


class _AsyncJsonParser:
    """
    Memory-efficient JSON parser that reads from an async iterable or stream.
    Allows filtering out unwanted keys from objects to save memory.
    """
    def __init__(self, stream_source, ignore_keys=None):
        if hasattr(stream_source, "read"):
            self.iterable = _ReaderIterable(stream_source)
        elif hasattr(stream_source, "__aiter__"):
            self.iterable = stream_source.__aiter__()
        else:
            self.iterable = stream_source
            
        self.ignore_keys = set(ignore_keys) if ignore_keys else ()
        self.buffer = bytearray()
        self.pos = 0
        self.keep_pos = None
        self.finished = False

    async def _fill_buffer(self, min_length=1):
        while len(self.buffer) - self.pos < min_length and not self.finished:
            # Drop consumed bytes to save memory (only when enough has accumulated
            # to justify the allocation cost of the bytearray slice)
            drop_pos = self.pos if self.keep_pos is None else self.keep_pos
            if drop_pos >= 256:
                self.buffer = self.buffer[drop_pos:]
                self.pos -= drop_pos
                if self.keep_pos is not None:
                    self.keep_pos -= drop_pos
            
            try:
                chunk = await self.iterable.__anext__()
                if chunk is None:
                    continue
                if isinstance(chunk, str):
                    chunk = chunk.encode('utf-8')
                self.buffer.extend(chunk)
            except StopAsyncIteration:
                self.finished = True
                break

    def _at_whitespace_or_buffer_end(self):
        return self.pos >= len(self.buffer) or self.buffer[self.pos] in b' \t\n\r'

    def _needs_fill(self, min_length):
        return len(self.buffer) - self.pos < min_length

    async def skip_whitespace(self):
        while True:
            self.pos = _viper_skip_whitespace(self.buffer, self.pos, len(self.buffer))
            if self.pos < len(self.buffer):
                return
            await self._fill_buffer(1)
            if self.pos >= len(self.buffer):
                return

    async def fast_skip_string(self):
        self.pos += 1
        self.keep_pos = self.pos
        try:
            while True:
                if self._needs_fill(1):
                    await self._fill_buffer(1)
                if self.pos >= len(self.buffer):
                    return

                buf = self.buffer
                buf_len = len(buf)
                quote_pos = buf.find(b'"', self.pos, buf_len)
                backslash_pos = buf.find(b'\\', self.pos, buf_len)

                if backslash_pos != -1 and (quote_pos == -1 or backslash_pos < quote_pos):
                    self.pos = backslash_pos
                    if self._needs_fill(2):
                        await self._fill_buffer(2)
                    if self.pos + 1 >= len(self.buffer):
                        self.pos = len(self.buffer)
                        return
                    self.pos += 2
                elif quote_pos != -1:
                    self.pos = quote_pos + 1
                    return
                else:
                    self.pos = buf_len

                if self.pos - self.keep_pos > 1024:
                    self.keep_pos = self.pos
        finally:
            self.keep_pos = None

    async def _skip_container(self, open_byte, close_byte):
        open_needle = bytes((open_byte,))
        close_needle = bytes((close_byte,))
        depth = 1
        self.pos += 1
        while depth > 0:
            if self._needs_fill(1):
                await self._fill_buffer(1)
            if self.pos >= len(self.buffer):
                return

            buf = self.buffer
            buf_len = len(buf)
            while self.pos < buf_len:
                open_pos = buf.find(open_needle, self.pos, buf_len)
                close_pos = buf.find(close_needle, self.pos, buf_len)
                quote_pos = buf.find(b'"', self.pos, buf_len)

                nearest = buf_len
                if open_pos != -1 and open_pos < nearest:
                    nearest = open_pos
                if close_pos != -1 and close_pos < nearest:
                    nearest = close_pos
                if quote_pos != -1 and quote_pos < nearest:
                    nearest = quote_pos

                self.pos = nearest
                if self.pos >= buf_len:
                    break

                c = buf[self.pos]
                if c == 0x22:
                    await self.fast_skip_string()
                    buf = self.buffer
                    buf_len = len(buf)
                    continue

                self.pos += 1
                if c == open_byte:
                    depth += 1
                else:
                    depth -= 1
                    if depth == 0:
                        return

    async def _skip_number_chars(self):
        while True:
            self.pos = _viper_skip_number_chars(self.buffer, self.pos, len(self.buffer))
            if self.pos < len(self.buffer):
                return
            await self._fill_buffer(1)
            if self.pos >= len(self.buffer):
                return

    async def fast_skip_value(self):
        if self._at_whitespace_or_buffer_end():
            await self.skip_whitespace()
        if self.pos >= len(self.buffer): return

        c = self.buffer[self.pos]
        if c == ord('{'):
            await self._skip_container(ord('{'), ord('}'))
        elif c == ord('['):
            await self._skip_container(ord('['), ord(']'))
        elif c == ord('"'):
            await self.fast_skip_string()
        elif c == ord('t'):
            if self._needs_fill(4):
                await self._fill_buffer(4)
            self.pos += 4
        elif c == ord('f'):
            if self._needs_fill(5):
                await self._fill_buffer(5)
            self.pos += 5
        elif c == ord('n'):
            if self._needs_fill(4):
                await self._fill_buffer(4)
            self.pos += 4
        else:
            await self._skip_number_chars()

    async def parse_value(self):
        if self._at_whitespace_or_buffer_end():
            await self.skip_whitespace()
        if self.pos >= len(self.buffer): return None
        
        c = self.buffer[self.pos]
        if c == ord('{'): return await self.parse_object()
        elif c == ord('['): return await self.parse_array()
        elif c == ord('"'): return await self.parse_string()
        elif c == ord('t'):
            if self._needs_fill(4):
                await self._fill_buffer(4)
            self.pos += 4
            return True
        elif c == ord('f'):
            if self._needs_fill(5):
                await self._fill_buffer(5)
            self.pos += 5
            return False
        elif c == ord('n'):
            if self._needs_fill(4):
                await self._fill_buffer(4)
            self.pos += 4
            return None
        elif c in b']}:,':
            raise ValueError(f"Unexpected character '{chr(c)}' at position {self.pos}")
        elif c in b'-+0123456789':
            return await self.parse_number()
        else:
            raise ValueError(f"Unexpected character '{chr(c)}' at position {self.pos}")

    async def parse_object(self):
        self.pos += 1 # skip '{'
        if self._at_whitespace_or_buffer_end():
            await self.skip_whitespace()
        
        obj = {}
        if self.pos < len(self.buffer) and self.buffer[self.pos] == ord('}'):
            self.pos += 1
            return obj
            
        while True:
            if self._at_whitespace_or_buffer_end():
                await self.skip_whitespace()
            if self.pos >= len(self.buffer) or self.buffer[self.pos] == ord('}'):
                # Reached end gracefully
                break

            key = None
            if self.buffer[self.pos] == ord('"'):
                key = await self.parse_string()

            if self._at_whitespace_or_buffer_end():
                await self.skip_whitespace()
            if self.pos < len(self.buffer) and self.buffer[self.pos] == ord(':'):
                self.pos += 1 # skip ':'

            if key in self.ignore_keys:
                await self.fast_skip_value()
            else:
                val = await self.parse_value()
                if key is not None:
                    obj[key] = val

            if self._at_whitespace_or_buffer_end():
                await self.skip_whitespace()
            if self.pos < len(self.buffer) and self.buffer[self.pos] == ord('}'):
                self.pos += 1
                break
            if self.pos < len(self.buffer) and self.buffer[self.pos] == ord(','):
                self.pos += 1 # skip ','
        return obj

    async def parse_array(self):
        self.pos += 1 # skip '['
        if self._at_whitespace_or_buffer_end():
            await self.skip_whitespace()

        arr = []
        if self.pos < len(self.buffer) and self.buffer[self.pos] == ord(']'):
            self.pos += 1
            return arr

        while True:
            if self._at_whitespace_or_buffer_end():
                await self.skip_whitespace()
            if self.pos >= len(self.buffer) or self.buffer[self.pos] == ord(']'):
                break

            val = await self.parse_value()
            arr.append(val)

            if self._at_whitespace_or_buffer_end():
                await self.skip_whitespace()
            if self.pos < len(self.buffer) and self.buffer[self.pos] == ord(']'):
                self.pos += 1
                break
            if self.pos < len(self.buffer) and self.buffer[self.pos] == ord(','):
                self.pos += 1 # skip ','
        return arr

    async def parse_string(self):
        self.pos += 1 # skip '"'
        self.keep_pos = self.pos

        try:
            # Lazy pieces list - only allocated for strings > 1024 bytes
            pieces = None
            closed = False

            while not closed:
                if self._needs_fill(1):
                    await self._fill_buffer(1)
                if self.pos >= len(self.buffer):
                    break

                buf = self.buffer
                buf_len = len(buf)
                quote_pos = buf.find(b'"', self.pos, buf_len)
                backslash_pos = buf.find(b'\\', self.pos, buf_len)

                if backslash_pos != -1 and (quote_pos == -1 or backslash_pos < quote_pos):
                    self.pos = backslash_pos
                    if self._needs_fill(2):
                        await self._fill_buffer(2)
                    if self.pos + 1 >= len(self.buffer):
                        self.pos = len(self.buffer)
                        break
                    self.pos += 2
                elif quote_pos != -1:
                    self.pos = quote_pos
                    closed = True
                else:
                    self.pos = buf_len

                if not closed and self.pos - self.keep_pos > 1024:
                    if pieces is None:
                        pieces = []
                    pieces.append(self.buffer[self.keep_pos:self.pos].decode('utf-8'))
                    self.keep_pos = self.pos

            segment = self.buffer[self.keep_pos:self.pos].decode('utf-8')
            val = "".join(pieces) + segment if pieces else segment

            if closed:
                self.pos += 1 # skip closing '"'
            return _unescape_string(val)
        finally:
            self.keep_pos = None

    async def parse_number(self):
        self.keep_pos = self.pos
        try:
            while True:
                self.pos = _viper_skip_number_chars(self.buffer, self.pos, len(self.buffer))
                if self.pos < len(self.buffer):
                    break
                await self._fill_buffer(1)
                if self.pos >= len(self.buffer):
                    break

            val = self.buffer[self.keep_pos:self.pos]
            if not val or val in (b'-', b'+'):
                raise ValueError(f"Expected number but got empty string near position {self.keep_pos}")
            if b'.' in val or b'e' in val or b'E' in val:
                return float(val)
            return int(val)
        finally:
            self.keep_pos = None


class _AsyncArrayIterator:
    """Iterator to return array elements from an async stream"""
    def __init__(self, parser):
        self.parser = parser
        self.started = False
        self.finished = False

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self.finished:
            raise StopAsyncIteration

        if not self.started:
            if self.parser._at_whitespace_or_buffer_end():
                await self.parser.skip_whitespace()
            if self.parser.pos >= len(self.parser.buffer) or self.parser.buffer[self.parser.pos] != ord('['):
                self.finished = True
                raise ValueError("Expected '[' at start of array")
            self.parser.pos += 1
            self.started = True

        if self.parser._at_whitespace_or_buffer_end():
            await self.parser.skip_whitespace()

        if self.parser.pos >= len(self.parser.buffer) or self.parser.buffer[self.parser.pos] == ord(']'):
            self.finished = True
            raise StopAsyncIteration

        val = await self.parser.parse_value()

        if self.parser._at_whitespace_or_buffer_end():
            await self.parser.skip_whitespace()
        if self.parser.pos < len(self.parser.buffer):
            c = self.parser.buffer[self.parser.pos]
            if c == ord(']'):
                self.parser.pos += 1
                self.finished = True
            elif c == ord(','):
                self.parser.pos += 1
                
        return val


# ==========================================
# Public API
# ==========================================

async def load(async_iterable, ignore_keys=None):
    """
    Parse a single top-level JSON object from an asynchronous stream, skipping unwanted fields.
    Useful for reading WebSockets block by block.
    """
    parser = _AsyncJsonParser(async_iterable, ignore_keys=ignore_keys)
    return await parser.parse_value()

def load_array(async_iterable):
    """
    Returns an async iterator that parses a flat JSON array from an async stream lazily.
    Yields array elements one by one.
    """
    parser = _AsyncJsonParser(async_iterable)
    return _AsyncArrayIterator(parser)
