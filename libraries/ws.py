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

    async def read_frame(self, max_size=None):
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

        if mask:  # Mask is 4 bytes
            mask_bits = await self.reader.readexactly(4)

        try:
            data = await self.reader.readexactly(length)
        except MemoryError:
            # We can't receive this many bytes, close the socket
            print("Frame of length %s too big. Closing" % length)
            await self.close(code=CLOSE_TOO_BIG)
            return True, OP_CLOSE, None

        if mask:
            # Unmask in-place to avoid creating new bytes object
            data_mv = memoryview(data)
            for i in range(len(data_mv)):
                data_mv[i] ^= mask_bits[i % 4]
            data = bytes(data_mv)

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

    async def recv(self):
        fin, opcode, data = await self.read_frame()

        if not fin:
            raise NotImplementedError("Not fin")

        if opcode == OP_TEXT:
            return data.decode('utf-8')
        elif opcode == OP_BYTES:
            return data
        elif opcode == OP_CLOSE:
            self.writer.close()
            raise ConnectionClosed()
        elif opcode == OP_PONG:
            return None
        elif opcode == OP_PING:
            await self.write_frame(OP_PONG, data)
            return None
        elif opcode == OP_CONT:
            raise NotImplementedError(opcode)
        else:
            raise ValueError(opcode)

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
