"""
Lean streaming JSON parser for flat arrays and general objects in MicroPython.
Parses elements one at a time without buffering the entire payload.
Designed for memory-constrained environments.
"""

def _unescape_string(s):
    if '\\' not in s:
        return s
    
    res = []
    i = 0
    length = len(s)
    while i < length:
        c = s[i]
        if c == '\\':
            i += 1
            if i >= length: break
            esc = s[i]
            if esc == '"': res.append('"')
            elif esc == '\\': res.append('\\')
            elif esc == '/': res.append('/')
            elif esc == 'b': res.append('\b')
            elif esc == 'f': res.append('\f')
            elif esc == 'n': res.append('\n')
            elif esc == 'r': res.append('\r')
            elif esc == 't': res.append('\t')
            elif esc == 'u':
                if i + 4 < length:
                    hex_str = s[i+1:i+5]
                    try:
                        res.append(chr(int(hex_str, 16)))
                    except ValueError:
                        pass
                    i += 4
            else:
                res.append('\\' + esc)
        else:
            res.append(c)
        i += 1
    return "".join(res)

def _parse_number_str(val_str, pos_hint=0):
    if not val_str or val_str in ('-', '+'):
        raise ValueError(f"Expected number but got empty string near position {pos_hint}")
    if '.' in val_str or 'e' in val_str or 'E' in val_str:
        return float(val_str)
    return int(val_str)

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
            
        self.ignore_keys = set(ignore_keys) if ignore_keys else set()
        self.buffer = bytearray()
        self.pos = 0
        self.keep_pos = None
        self.finished = False

    async def _fill_buffer(self, min_length=1):
        while len(self.buffer) - self.pos < min_length and not self.finished:
            # Drop consumed bytes to save memory
            drop_pos = self.pos if self.keep_pos is None else self.keep_pos
            if drop_pos > 0:
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

    async def skip_whitespace(self):
        while True:
            await self._fill_buffer(1)
            if self.pos >= len(self.buffer):
                break
            if self.buffer[self.pos] not in b' \t\n\r':
                break
            self.pos += 1

    async def fast_skip_string(self):
        self.pos += 1
        self.keep_pos = self.pos
        try:
            escaped = False
            while True:
                await self._fill_buffer(1)
                if self.pos >= len(self.buffer):
                    return
                
                c = self.buffer[self.pos]
                if escaped:
                    escaped = False
                elif c == ord('\\'):
                    escaped = True
                elif c == ord('"'):
                    self.pos += 1
                    return
                
                self.pos += 1
                
                # Periodically flush to keep memory small if string is huge
                if self.pos - self.keep_pos > 1024:
                    self.keep_pos = self.pos
        finally:
            self.keep_pos = None

    async def fast_skip_value(self):
        await self.skip_whitespace()
        if self.pos >= len(self.buffer): return
        
        c = self.buffer[self.pos]
        if c == ord('{'):
            depth = 1
            self.pos += 1
            while depth > 0:
                await self._fill_buffer(1)
                if self.pos >= len(self.buffer):
                    break
                c2 = self.buffer[self.pos]
                if c2 == ord('"'): 
                    await self.fast_skip_string()
                elif c2 == ord('{'):
                    depth += 1
                    self.pos += 1
                elif c2 == ord('}'):
                    depth -= 1
                    self.pos += 1
                else:
                    self.pos += 1
        elif c == ord('['):
            depth = 1
            self.pos += 1
            while depth > 0:
                await self._fill_buffer(1)
                if self.pos >= len(self.buffer):
                    break
                c2 = self.buffer[self.pos]
                if c2 == ord('"'): 
                    await self.fast_skip_string()
                elif c2 == ord('['):
                    depth += 1
                    self.pos += 1
                elif c2 == ord(']'):
                    depth -= 1
                    self.pos += 1
                else:
                    self.pos += 1
        elif c == ord('"'):
            await self.fast_skip_string()
        elif c == ord('t'): 
            await self._fill_buffer(4)
            self.pos += 4
        elif c == ord('f'): 
            await self._fill_buffer(5)
            self.pos += 5
        elif c == ord('n'): 
            await self._fill_buffer(4)
            self.pos += 4
        else:
            while True:
                await self._fill_buffer(1)
                if self.pos >= len(self.buffer) or self.buffer[self.pos] not in b'-+0123456789.eE':
                    break
                self.pos += 1

    async def parse_value(self):
        await self.skip_whitespace()
        if self.pos >= len(self.buffer): return None
        
        c = self.buffer[self.pos]
        if c == ord('{'): return await self.parse_object()
        elif c == ord('['): return await self.parse_array()
        elif c == ord('"'): return await self.parse_string()
        elif c == ord('t'): 
            await self._fill_buffer(4)
            self.pos += 4
            return True
        elif c == ord('f'): 
            await self._fill_buffer(5)
            self.pos += 5
            return False
        elif c == ord('n'): 
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
        await self.skip_whitespace()
        
        obj = {}
        if self.pos < len(self.buffer) and self.buffer[self.pos] == ord('}'):
            self.pos += 1
            return obj
            
        while True:
            await self.skip_whitespace()
            await self._fill_buffer(1)
            if self.pos >= len(self.buffer) or self.buffer[self.pos] == ord('}'):
                # Reached end gracefully
                break
                
            key = None
            if self.buffer[self.pos] == ord('"'):
                key = await self.parse_string()
                
            await self.skip_whitespace()
            await self._fill_buffer(1)
            if self.pos < len(self.buffer) and self.buffer[self.pos] == ord(':'):
                self.pos += 1 # skip ':'
            
            if key in self.ignore_keys:
                await self.fast_skip_value()
            else:
                val = await self.parse_value()
                if key is not None:
                    obj[key] = val
                
            await self.skip_whitespace()
            await self._fill_buffer(1)
            if self.pos < len(self.buffer) and self.buffer[self.pos] == ord('}'):
                self.pos += 1
                break
            if self.pos < len(self.buffer) and self.buffer[self.pos] == ord(','):
                self.pos += 1 # skip ','
        return obj

    async def parse_array(self):
        self.pos += 1 # skip '['
        await self.skip_whitespace()
        
        arr = []
        if self.pos < len(self.buffer) and self.buffer[self.pos] == ord(']'):
            self.pos += 1
            return arr
            
        while True:
            await self.skip_whitespace()
            await self._fill_buffer(1)
            if self.pos >= len(self.buffer) or self.buffer[self.pos] == ord(']'):
                break
                
            val = await self.parse_value()
            arr.append(val)
            
            await self.skip_whitespace()
            await self._fill_buffer(1)
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
            # Buffer string pieces to avoid tracking large string slices
            pieces = []
            escaped = False
            
            while True:
                await self._fill_buffer(1)
                if self.pos >= len(self.buffer):
                    break
                    
                c = self.buffer[self.pos]
                if escaped:
                    escaped = False
                elif c == ord('\\'):
                    escaped = True
                elif c == ord('"'):
                    pieces.append(self.buffer[self.keep_pos:self.pos].decode('utf-8'))
                    break
                    
                self.pos += 1
                
                # Periodically flush pieces to keep memory small if string is huge
                if self.pos - self.keep_pos > 1024:
                    pieces.append(self.buffer[self.keep_pos:self.pos].decode('utf-8'))
                    self.keep_pos = self.pos
                    
            val = "".join(pieces)
            
            self.pos += 1 # skip closing '"'
            return _unescape_string(val)
        finally:
            self.keep_pos = None

    async def parse_number(self):
        self.keep_pos = self.pos
        try:
            while True:
                await self._fill_buffer(1)
                if self.pos >= len(self.buffer):
                    break
                # Use ASCII check to avoid large substrings
                c = self.buffer[self.pos]
                if c not in b'-+0123456789.eE':
                    break
                self.pos += 1
                
            val_str = self.buffer[self.keep_pos:self.pos].decode('ascii')
            return _parse_number_str(val_str, pos_hint=self.keep_pos)
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
            await self.parser.skip_whitespace()
            await self.parser._fill_buffer(1)
            if self.parser.pos >= len(self.parser.buffer) or self.parser.buffer[self.parser.pos] != ord('['):
                self.finished = True
                raise ValueError("Expected '[' at start of array")
            self.parser.pos += 1
            self.started = True

        await self.parser.skip_whitespace()
        await self.parser._fill_buffer(1)
        
        if self.parser.pos >= len(self.parser.buffer) or self.parser.buffer[self.parser.pos] == ord(']'):
            self.finished = True
            raise StopAsyncIteration

        val = await self.parser.parse_value()

        await self.parser.skip_whitespace()
        await self.parser._fill_buffer(1)
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
