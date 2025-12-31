"""
Lean streaming JSON parser for flat arrays in MicroPython.
Parses elements one at a time without buffering the entire array.
Designed for memory-constrained environments.
"""

class FlatJsonParser:
    """
    Streaming parser for flat JSON arrays containing primitives (numbers, strings, booleans, null).
    Does not support nested objects or arrays - only top-level array elements.

    Usage:
        async for element in FlatJsonParser(reader):
            process(element)
    """

    def __init__(self, reader):
        """
        Initialize parser with an async reader (e.g., StreamReader from asyncio.open_connection).

        Args:
            reader: An async reader with a read(n) method that returns bytes
        """
        self.reader = reader
        self.buffer = bytearray()
        self.pos = 0
        self.started = False
        self.finished = False
        # Pre-allocate reusable buffers to reduce allocations
        self._string_buf = bytearray(256)  # For parsing strings
        self._number_buf = bytearray(32)   # For parsing numbers

    async def _read_byte(self):
        """Read a single byte, buffering if necessary."""
        if self.pos >= len(self.buffer):
            chunk = await self.reader.read(64)  # Read in small chunks
            if not chunk:
                return None
            self.buffer = bytearray(chunk)
            self.pos = 0

        byte = self.buffer[self.pos]
        self.pos += 1
        return byte

    async def _skip_whitespace(self):
        """Skip whitespace characters."""
        while True:
            b = await self._read_byte()
            if b is None:
                return None
            if b not in (0x20, 0x09, 0x0A, 0x0D):  # space, tab, newline, carriage return
                return b

    async def _parse_string(self):
        """Parse a JSON string. Assumes opening quote already consumed."""
        # Reuse pre-allocated buffer
        result_len = 0
        escaped = False

        while True:
            b = await self._read_byte()
            if b is None:
                raise ValueError("Unexpected end in string")

            if escaped:
                # Handle escape sequences
                if b == ord('n'):
                    char_byte = ord('\n')
                elif b == ord('t'):
                    char_byte = ord('\t')
                elif b == ord('r'):
                    char_byte = ord('\r')
                elif b == ord('b'):
                    char_byte = ord('\b')
                elif b == ord('f'):
                    char_byte = ord('\f')
                elif b == ord('"'):
                    char_byte = ord('"')
                elif b == ord('\\'):
                    char_byte = ord('\\')
                elif b == ord('/'):
                    char_byte = ord('/')
                elif b == ord('u'):
                    # Unicode escape - read 4 hex digits
                    hex_chars = bytearray(4)
                    for i in range(4):
                        hb = await self._read_byte()
                        if hb is None:
                            raise ValueError("Unexpected end in unicode escape")
                        hex_chars[i] = hb
                    # Convert hex to int and then to UTF-8
                    try:
                        code_point = int(hex_chars.decode('ascii'), 16)
                        # Simple UTF-8 encoding for common range
                        if code_point < 0x80:
                            if result_len >= len(self._string_buf):
                                self._string_buf.extend(bytearray(256))
                            self._string_buf[result_len] = code_point
                            result_len += 1
                        elif code_point < 0x800:
                            if result_len + 2 >= len(self._string_buf):
                                self._string_buf.extend(bytearray(256))
                            self._string_buf[result_len] = 0xC0 | (code_point >> 6)
                            self._string_buf[result_len + 1] = 0x80 | (code_point & 0x3F)
                            result_len += 2
                        else:
                            if result_len + 3 >= len(self._string_buf):
                                self._string_buf.extend(bytearray(256))
                            self._string_buf[result_len] = 0xE0 | (code_point >> 12)
                            self._string_buf[result_len + 1] = 0x80 | ((code_point >> 6) & 0x3F)
                            self._string_buf[result_len + 2] = 0x80 | (code_point & 0x3F)
                            result_len += 3
                    except:
                        raise ValueError("Invalid unicode escape")
                    escaped = False
                    continue
                else:
                    # Unknown escape, keep as-is
                    char_byte = b

                if result_len >= len(self._string_buf):
                    self._string_buf.extend(bytearray(256))
                self._string_buf[result_len] = char_byte
                result_len += 1
                escaped = False
            elif b == ord('\\'):
                escaped = True
            elif b == ord('"'):
                # End of string - decode only the used portion
                # MicroPython: convert memoryview to bytes via bytearray
                return bytes(self._string_buf[:result_len]).decode('utf-8')
            else:
                if result_len >= len(self._string_buf):
                    self._string_buf.extend(bytearray(256))
                self._string_buf[result_len] = b
                result_len += 1

    async def _parse_number(self, first_byte):
        """Parse a JSON number. First byte already read."""
        # Reuse pre-allocated number buffer
        self._number_buf[0] = first_byte
        num_len = 1

        while True:
            b = await self._read_byte()
            if b is None:
                break

            # Number characters: 0-9, -, +, ., e, E
            if b in (0x2D, 0x2B, 0x2E, 0x45, 0x65) or (0x30 <= b <= 0x39):
                if num_len >= len(self._number_buf):
                    self._number_buf.extend(bytearray(16))
                self._number_buf[num_len] = b
                num_len += 1
            else:
                # Put byte back by moving position back
                self.pos -= 1
                break

        # Decode only the used portion
        # MicroPython: convert memoryview to bytes via bytearray
        num_str = bytes(self._number_buf[:num_len]).decode('ascii')

        # Parse as int or float
        if '.' in num_str or 'e' in num_str or 'E' in num_str:
            return float(num_str)
        else:
            return int(num_str)

    async def _parse_literal(self, first_byte, expected, value):
        """Parse a literal (true, false, null). First byte already read."""
        for i in range(1, len(expected)):
            b = await self._read_byte()
            if b is None or b != ord(expected[i]):
                raise ValueError(f"Invalid literal, expected {expected}")
        return value

    async def _parse_element(self):
        """Parse a single array element."""
        b = await self._skip_whitespace()

        if b is None:
            return None

        # String
        if b == ord('"'):
            return await self._parse_string()

        # Number (starts with digit or minus)
        elif (0x30 <= b <= 0x39) or b == 0x2D:
            return await self._parse_number(b)

        # true
        elif b == ord('t'):
            return await self._parse_literal(b, 'true', True)

        # false
        elif b == ord('f'):
            return await self._parse_literal(b, 'false', False)

        # null
        elif b == ord('n'):
            return await self._parse_literal(b, 'null', None)

        # End of array
        elif b == ord(']'):
            self.finished = True
            return None

        # Comma (between elements)
        elif b == ord(','):
            # Skip comma and parse next element
            return await self._parse_element()

        else:
            raise ValueError(f"Unexpected character: {chr(b)}")

    def __aiter__(self):
        return self

    async def __anext__(self):
        """Async iterator protocol - yield next array element."""
        if self.finished:
            raise StopAsyncIteration

        # First call - skip to opening bracket
        if not self.started:
            b = await self._skip_whitespace()
            if b != ord('['):
                raise ValueError("Expected '[' at start of array")
            self.started = True

        # Parse next element
        element = await self._parse_element()

        if element is None and self.finished:
            raise StopAsyncIteration

        return element


def parse_flat_json_array(reader):
    """
    Convenience function to parse a flat JSON array from a reader.

    Args:
        reader: An async reader with a read(n) method

    Returns:
        FlatJsonParser instance (async iterator)

    Example:
        reader, writer = await asyncio.open_connection(host, port)
        # ... send HTTP request and skip headers ...
        async for element in parse_flat_json_array(reader):
            print(element)
    """
    return FlatJsonParser(reader)
