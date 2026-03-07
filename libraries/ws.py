import binascii
import random
import struct
import asyncio
from httpstream import parse_url

try:
    from micropython import const
except ImportError:
    const = lambda x : x

# Opcodes
OP_CONT = const(0x0)
OP_TEXT = const(0x1)
OP_BYTES = const(0x2)
OP_CLOSE = const(0x8)
OP_PING = const(0x9)
OP_PONG = const(0xa)

# Close codes
CLOSE_OK = const(1000)
CLOSE_GOING_AWAY = const(1001)
CLOSE_PROTOCOL_ERROR = const(1002)
CLOSE_DATA_NOT_SUPPORTED = const(1003)
CLOSE_BAD_DATA = const(1007)
CLOSE_POLICY_VIOLATION = const(1008)
CLOSE_TOO_BIG = const(1009)
CLOSE_MISSING_EXTN = const(1010)
CLOSE_BAD_CONDITION = const(1011)

class ConnectionClosed(Exception):
    def __init__(self):
        super().__init__("Connection closed")

class _FrameDataReader:
    """Class-based async iterator for reading WebSocket frame data chunks."""
    def __init__(self, reader, length, mask_bits, close_callback, chunk_size=128):
        self.reader = reader
        self.length = length
        self.mask_bits = mask_bits
        self.close_callback = close_callback
        self.chunk_size = chunk_size
        self.bytes_read = 0

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self.bytes_read >= self.length:
            raise StopAsyncIteration

        to_read = min(self.chunk_size, self.length - self.bytes_read)
        try:
            data = await self.reader.readexactly(to_read)
        except MemoryError:
            print("Frame of length %s too big. Closing" % self.length)
            await self.close_callback(code=CLOSE_TOO_BIG)
            self.bytes_read = self.length
            raise StopAsyncIteration

        if self.mask_bits:
            data_mv = memoryview(data)
            for i in range(len(data_mv)):
                data_mv[i] ^= self.mask_bits[(self.bytes_read + i) % 4]
            data = bytes(data_mv)

        self.bytes_read += to_read
        return data

class _RecvStream:
    """Class-based async iterator for receiving decoded WebSocket messages."""
    def __init__(self, ws):
        self.ws = ws
        self._data_reader = None
        self._opcode = None
        self._initialized = False
        self._finished = False

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self._finished:
            raise StopAsyncIteration

        if not self._initialized:
            self._initialized = True
            fin, opcode, length, mask_bits = await self.ws._read_frame_header()

            if not fin:
                raise NotImplementedError("Not fin")

            self._opcode = opcode

            if opcode in (OP_TEXT, OP_BYTES):
                self._data_reader = _FrameDataReader(
                    self.ws.reader, length, mask_bits, self.ws.close
                )
            elif opcode == OP_CLOSE:
                self.ws.writer.close()
                raise ConnectionClosed()
            elif opcode == OP_PONG:
                self._finished = True
                return None
            elif opcode == OP_PING:
                data_reader = _FrameDataReader(
                    self.ws.reader, length, mask_bits, self.ws.close
                )
                chunks = []
                async for chunk in data_reader:
                    chunks.append(chunk)
                data = b''.join(chunks)
                await self.ws.write_frame(OP_PONG, data)
                self._finished = True
                return None
            elif opcode == OP_CONT:
                raise NotImplementedError(opcode)
            else:
                raise ValueError(opcode)

        # Stream data chunks for TEXT/BYTES
        try:
            data = await self._data_reader.__anext__()
            if self._opcode == OP_TEXT:
                return data.decode('utf-8')
            return data
        except StopAsyncIteration:
            self._finished = True
            raise

class Websocket:
    is_client = False

    def __init__(self, reader, writer):
        self.reader = reader
        self.writer = writer

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.close()

    def settimeout(self, timeout):
        self.sock.settimeout(timeout)

    async def _read_frame_header(self, chunk_size=128):
        """Parse the WebSocket frame header. Returns (fin, opcode, length, mask_bits)."""
        two_bytes = await self.reader.readexactly(2)

        byte1, byte2 = struct.unpack('!BB', two_bytes)

        # Byte 1: FIN(1) _(1) _(1) _(1) OPCODE(4)
        fin = bool(byte1 & 0x80)
        opcode = byte1 & 0x0f

        # Byte 2: MASK(1) LENGTH(7)
        mask = bool(byte2 & (1 << 7))
        length = byte2 & 0x7f

        if length == 126:  # Magic number, length header is 2 bytes
            length, = struct.unpack('!H', await self.reader.readexactly(2))
        elif length == 127:  # Magic number, length header is 8 bytes
            length, = struct.unpack('!Q', await self.reader.readexactly(8))

        mask_bits = None
        if mask:  # Mask is 4 bytes
            mask_bits = await self.reader.readexactly(4)

        return fin, opcode, length, mask_bits

    async def read_frame(self, max_size=None):
        fin, opcode, length, mask_bits = await self._read_frame_header()

        chunks = []
        data_reader = _FrameDataReader(self.reader, length, mask_bits, self.close)
        async for chunk in data_reader:
            chunks.append(chunk)

        data = b''.join(chunks) if chunks else b''
        return fin, opcode, data

    async def write_frame(self, opcode, data=b''):
        fin = True
        mask = self.is_client  # messages sent by client are masked

        length = len(data)

        # Frame header
        # Byte 1: FIN(1) _(1) _(1) _(1) OPCODE(4)
        byte1 = 0x80 if fin else 0
        byte1 |= opcode

        # Byte 2: MASK(1) LENGTH(7)
        byte2 = 0x80 if mask else 0

        if length < 126:  # 126 is magic value to use 2-byte length header
            byte2 |= length
            self.writer.write(struct.pack('!BB', byte1, byte2))
        elif length < (1 << 16):  # Length fits in 2-bytes
            byte2 |= 126  # Magic code
            self.writer.write(struct.pack('!BBH', byte1, byte2, length))
        elif length < (1 << 64):
            byte2 |= 127  # Magic code
            self.writer.write(struct.pack('!BBQ', byte1, byte2, length))
        else:
            raise ValueError("Length could not be encoded")

        if mask:  # Mask is 4 bytes
            mask_bits = struct.pack('!I', random.getrandbits(32))
            self.writer.write(mask_bits)

            data = bytes(b ^ mask_bits[i % 4]
                         for i, b in enumerate(data))

        self.writer.write(data)
        await self.writer.drain()

    def recv_stream(self):
        return _RecvStream(self)

    async def recv(self):
        chunks = []
        async for chunk in self.recv_stream():
            if chunk is not None:
                chunks.append(chunk)

        if not chunks:
            return None
        
        if isinstance(chunks[0], str):
            return ''.join(chunks)
        else:
            return b''.join(chunks)

    async def send(self, buf):
        if isinstance(buf, str):
            opcode = OP_TEXT
            buf = buf.encode('utf-8')
        elif isinstance(buf, bytes):
            opcode = OP_BYTES
        else:
            raise TypeError("Unknown data type")

        await self.write_frame(opcode, buf)

    async def close(self, code=CLOSE_OK, reason=''):
        buf = struct.pack('!H', code) + reason.encode('utf-8')

        try:
            # This could fail if the socket is broken
            await self.write_frame(OP_CLOSE, buf)
        except:
            pass

        self.writer.close()
        await self.writer.wait_closed()
        
class WebsocketClient(Websocket):
    is_client = True

async def connect(uri):
    uri = parse_url(uri)
    assert uri

    print("open connection %s:%s" % (uri.hostname, uri.port))
    
    reader, writer = await asyncio.open_connection(uri.hostname, uri.port, ssl = uri.port == 443)
    
    try:
        # Sec-WebSocket-Key is 16 bytes of random base64 encoded
        key = binascii.b2a_base64(bytes(random.getrandbits(8)
                                        for _ in range(16)))[:-1]

        writer.write(b'GET %s HTTP/1.1\r\n' % (uri.path or '/').encode('utf-8'))
        writer.write(b'Host: %s:%i\r\n' % (uri.hostname.encode('utf-8'), uri.port))
        writer.write(b'Connection: Upgrade\r\n')
        writer.write(b'Upgrade: websocket\r\n')
        writer.write(b'Sec-WebSocket-Key: %s\r\n' % key)
        writer.write(b'Sec-WebSocket-Version: 13\r\n')
        writer.write(b'Origin: %s://%s:%i\r\n' % (b'http', uri.hostname.encode('utf-8'), uri.port))
        writer.write(b'\r\n')
        await writer.drain()
        
        line = await reader.readline()

        header = line[:-2]
        assert header.startswith(b'HTTP/1.1 101 '), header

        while header is not None:
            header = await reader.readline()
            if header == b'\r\n':
                break

        return WebsocketClient(reader, writer)
    except Exception:
        writer.close()
        await writer.wait_closed()
        raise
