import ubinascii as binascii
import urandom as random
import ssl

import ure as re
import ustruct as struct
import urandom as random
import usocket as socket
from ucollections import namedtuple

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


class Websocket:
    """
    Basis of the Websocket protocol.

    This can probably be replaced with the C-based websocket module, but
    this one currently supports more options.
    """
    is_client = False

    def __init__(self, sock):
        self.sock = sock
        #self.open = True

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
        two_bytes = self.sock.read(2)

        if not two_bytes:
            raise NoDataException

        byte1, byte2 = struct.unpack('!BB', two_bytes)

        # Byte 1: FIN(1) _(1) _(1) _(1) OPCODE(4)
        fin = bool(byte1 & 0x80)
        opcode = byte1 & 0x0f

        # Byte 2: MASK(1) LENGTH(7)
        mask = bool(byte2 & (1 << 7))
        length = byte2 & 0x7f

        if length == 126:  # Magic number, length header is 2 bytes
            length, = struct.unpack('!H', self.sock.read(2))
        elif length == 127:  # Magic number, length header is 8 bytes
            length, = struct.unpack('!Q', self.sock.read(8))

        if mask:  # Mask is 4 bytes
            mask_bits = self.sock.read(4)

        try:
            data = self.sock.read(length)
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
            self.sock.write(struct.pack('!BB', byte1, byte2))
        elif length < (1 << 16):  # Length fits in 2-bytes
            byte2 |= 126  # Magic code
            self.sock.write(struct.pack('!BBH', byte1, byte2, length))
        elif length < (1 << 64):
            byte2 |= 127  # Magic code
            self.sock.write(struct.pack('!BBQ', byte1, byte2, length))
        else:
            raise ValueError("Length could not be encoded")

        if mask:  # Mask is 4 bytes
            mask_bits = struct.pack('!I', random.getrandbits(32))
            self.sock.write(mask_bits)

            data = bytes(b ^ mask_bits[i % 4]
                         for i, b in enumerate(data))

        self.sock.write(data)

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
        if not self.open:
            return

        buf = struct.pack('!H', code) + reason.encode('utf-8')

        self.write_frame(OP_CLOSE, buf)
        self.sock.close()
        
class WebsocketClient(Websocket):
    is_client = True

def connect(uri):
    uri = urlparse(uri)
    assert uri

    print("open connection %s:%s" % (uri.hostname, uri.port))

    sock = socket.socket()
    sock.setblocking(False)
    addr = socket.getaddrinfo(uri.hostname, uri.port)
    
    try:
        sock.connect(addr[0][4])
    except OSError:
        pass
    
    if uri.protocol == 'wss':
        sock = ssl.wrap_socket(sock, server_hostname=uri.hostname)

    def send_header(header, *args):
        header_value = header % args + '\r\n'
        print(header_value)
        sock.write(header_value)
    
    # Sec-WebSocket-Key is 16 bytes of random base64 encoded
    key = binascii.b2a_base64(bytes(random.getrandbits(8)
                                    for _ in range(16)))[:-1]

    send_header(b'GET %s HTTP/1.1', uri.path or '/')
    send_header(b'Host: %s:%s', uri.hostname, uri.port)
    send_header(b'Connection: Upgrade')
    send_header(b'Upgrade: websocket')
    send_header(b'Sec-WebSocket-Key: %s', key)
    send_header(b'Sec-WebSocket-Version: 13')
    send_header(b'Origin: http://{hostname}:{port}'.format(
        hostname=uri.hostname,
        port=uri.port)
    )
    send_header(b'')
    
    line = None    
    while line is None:
        line = sock.readline()    

    header = line[:-2]
    assert header.startswith(b'HTTP/1.1 101 '), header

    # We don't (currently) need these headers
    # FIXME: should we check the return key?
    while header:
        print(str(header))
        header = sock.readline()[:-2]

    return WebsocketClient(sock)
