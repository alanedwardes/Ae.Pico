import ssl
import binascii
import random
import re
import errno
import struct
import socket
from collections import namedtuple

try:
    ssl_context = ssl.create_default_context()
    const = lambda x: x
    socket_makefile = lambda x: x.makefile()
except AttributeError:
    socket_makefile = lambda x: x
    ssl_context = ssl

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

URL_RE = re.compile(r'(wss|ws)://([A-Za-z0-9-\.]+)(?:\:([0-9]+))?(/.+)?')
URI = namedtuple('URI', ('protocol', 'hostname', 'port', 'path'))

class NoDataException(Exception):
    def __init__(self):
        super().__init__("No data")

class ConnectionClosed(Exception):
    def __init__(self):
        super().__init__("Connection closed")

def urlparse(uri):
    """Parse ws:// URLs"""
    match = URL_RE.match(uri)
    if match:
        protocol = match.group(1)
        host = match.group(2)
        port = match.group(3)
        path = match.group(4)

        if protocol == 'wss':
            if port is None:
                port = 443
        elif protocol == 'ws':
            if port is None:
                port = 80
        else:
            raise ValueError('Scheme {} is invalid'.format(protocol))

        return URI(protocol, host, int(port), path)

def _send(sock, msg):
    totalsent = 0
    length = len(msg)
    while totalsent < length:
        sent = sock.send(msg[totalsent:])
        if sent == 0:
            raise RuntimeError("socket connection broken")
        totalsent = totalsent + sent

def _recv(sock, length):
    chunks = []
    bytes_recd = 0
    while bytes_recd < length:
        chunk = sock.recv(min(length - bytes_recd, 2048))
        if chunk == b'':
            raise RuntimeError("socket connection broken")
        chunks.append(chunk)
        bytes_recd = bytes_recd + len(chunk)
    return b''.join(chunks)

class Websocket:
    is_client = False

    def __init__(self, sock):
        self.sock = sock

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()

    def settimeout(self, timeout):
        self.sock.settimeout(timeout)

    def read_frame(self, max_size=None):
        """
        Read a frame from the socket.
        See https://tools.ietf.org/html/rfc6455#section-5.2 for the details.
        """

        # Frame header
        two_bytes = None
        try:
            two_bytes = _recv(self.sock, 2)
        except OSError as e:
            if e.errno is errno.EAGAIN or \
                e.__class__.__name__ == 'SSLWantReadError' or \
                e.__class__.__name__ == 'BlockingIOError':
                raise NoDataException
            else:
                raise

        byte1, byte2 = struct.unpack('!BB', two_bytes)

        # Byte 1: FIN(1) _(1) _(1) _(1) OPCODE(4)
        fin = bool(byte1 & 0x80)
        opcode = byte1 & 0x0f

        # Byte 2: MASK(1) LENGTH(7)
        mask = bool(byte2 & (1 << 7))
        length = byte2 & 0x7f

        if length == 126:  # Magic number, length header is 2 bytes
            length, = struct.unpack('!H', _recv(self.sock, 2))
        elif length == 127:  # Magic number, length header is 8 bytes
            length, = struct.unpack('!Q', _recv(self.sock, 8))

        if mask:  # Mask is 4 bytes
            mask_bits = _recv(self.sock, 4)

        try:
            data = _recv(self.sock, length)
        except MemoryError:
            # We can't receive this many bytes, close the socket
            print("Frame of length %s too big. Closing" % length)
            self.close(code=CLOSE_TOO_BIG)
            print(fin, opcode, data)
            return True, OP_CLOSE, None

        if mask:
            data = bytes(b ^ mask_bits[i % 4]
                         for i, b in enumerate(data))

        return fin, opcode, data

    def write_frame(self, opcode, data=b''):
        """
        Write a frame to the socket.
        See https://tools.ietf.org/html/rfc6455#section-5.2 for the details.
        """
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
            _send(self.sock, struct.pack('!BB', byte1, byte2))
        elif length < (1 << 16):  # Length fits in 2-bytes
            byte2 |= 126  # Magic code
            _send(self.sock, struct.pack('!BBH', byte1, byte2, length))
        elif length < (1 << 64):
            byte2 |= 127  # Magic code
            _send(self.sock, struct.pack('!BBQ', byte1, byte2, length))
        else:
            raise ValueError("Length could not be encoded")

        if mask:  # Mask is 4 bytes
            mask_bits = struct.pack('!I', random.getrandbits(32))
            _send(self.sock, mask_bits)

            data = bytes(b ^ mask_bits[i % 4]
                         for i, b in enumerate(data))

        _send(self.sock, data)

    def recv(self):
        try:
            fin, opcode, data = self.read_frame()
        except ValueError:
            print("Failed to read frame. Socket dead.")
            self.sock.close()
            raise ConnectionClosed()

        if not fin:
            raise NotImplementedError("Not fin")

        if opcode == OP_TEXT:
            return data.decode('utf-8')
        elif opcode == OP_BYTES:
            return data
        elif opcode == OP_CLOSE:
            self.sock.close()
            raise ConnectionClosed()
        elif opcode == OP_PONG:
            raise NoDataException
        elif opcode == OP_PING:
            self.write_frame(OP_PONG, data)
            raise NoDataException
        elif opcode == OP_CONT:
            raise NotImplementedError(opcode)
        else:
            raise ValueError(opcode)

    def send(self, buf):
        if isinstance(buf, str):
            opcode = OP_TEXT
            buf = buf.encode('utf-8')
        elif isinstance(buf, bytes):
            opcode = OP_BYTES
        else:
            raise TypeError("Unknown data type")

        self.write_frame(opcode, buf)

    def close(self, code=CLOSE_OK, reason=''):
        buf = struct.pack('!H', code) + reason.encode('utf-8')

        try:
            # This could fail if the socket is broken
            self.write_frame(OP_CLOSE, buf)
        except:
            pass

        self.sock.close()
        
class WebsocketClient(Websocket):
    is_client = True

def connect(uri, timeout_seconds = 2):
    uri = urlparse(uri)
    assert uri

    print("open connection %s:%s" % (uri.hostname, uri.port))

    sock = socket.socket()
    sock.settimeout(timeout_seconds)
    addr = socket.getaddrinfo(uri.hostname, uri.port)
    sock.connect(addr[0][4])
    
    if uri.protocol == 'wss':
        sock = ssl_context.wrap_socket(sock, server_hostname=uri.hostname)
    
    # Sec-WebSocket-Key is 16 bytes of random base64 encoded
    key = binascii.b2a_base64(bytes(random.getrandbits(8)
                                    for _ in range(16)))[:-1]

    _send(sock, b'GET %s HTTP/1.1\r\n' % (uri.path.encode('utf-8') or b'/'))
    _send(sock, b'Host: %s:%i\r\n' % (uri.hostname.encode('utf-8'), uri.port))
    _send(sock, b'Connection: Upgrade\r\n')
    _send(sock, b'Upgrade: websocket\r\n')
    _send(sock, b'Sec-WebSocket-Key: %s\r\n' % key)
    _send(sock, b'Sec-WebSocket-Version: 13\r\n')
    _send(sock, b'Origin: %s://%s:%i\r\n' % (b'http', uri.hostname.encode('utf-8'), uri.port))
    _send(sock, b'\r\n')
    
    file = socket_makefile(sock)
    
    line = None    
    while line is None:
        line = file.readline()

    header = line[:-2]
    assert header.startswith('HTTP/1.1 101 '), header

    while header:
        header = file.readline()[:-2]

    sock.setblocking(False)

    return WebsocketClient(sock)
