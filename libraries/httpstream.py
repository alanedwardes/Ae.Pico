from collections import namedtuple

URI = namedtuple('URI', ('hostname', 'port', 'path', 'secure', 'protocol'))

def parse_url(url):
    """
    Parse a URL into its components using string operations instead of regex.
    
    Args:
        url (str): The URL to parse
        
    Returns:
        URI: Named tuple with (hostname, port, path, secure, protocol) where:
            - hostname (str): The hostname
            - port (int): The port number
            - path (str): The path (defaults to '/' if None)
            - secure (bool): True if HTTPS/WSS, False if HTTP/WS/NTP
            - protocol (str): The protocol scheme (http, https, ws, wss, ntp)
            
    Raises:
        ValueError: If the URL format is invalid or scheme is not supported
    """
    # Find the protocol
    protocol_end = url.find('://')
    if protocol_end == -1:
        raise ValueError('Invalid URL format')
    
    protocol = url[:protocol_end]
    if protocol not in ('http', 'https', 'ws', 'wss', 'ntp'):
        raise ValueError('Scheme {} is invalid'.format(protocol))
    
    # Get the rest after protocol://
    rest = url[protocol_end + 3:]
    
    # Find the first slash to separate host:port from path
    slash_pos = rest.find('/')
    if slash_pos == -1:
        # No path, everything is host:port
        host_port = rest
        path = '/'
    else:
        host_port = rest[:slash_pos]
        path = rest[slash_pos:]
    
    # Split host and port
    colon_pos = host_port.rfind(':')
    if colon_pos == -1:
        # No port specified
        host = host_port
        port = None
    else:
        # Check if the part after colon is a valid port number
        port_str = host_port[colon_pos + 1:]
        if port_str.isdigit():
            host = host_port[:colon_pos]
            port = int(port_str)
        else:
            # Colon is part of hostname (like IPv6), no port
            host = host_port
            port = None
    
    # Set default ports based on protocol
    if port is None:
        if protocol in ('https', 'wss'):
            port = 443
        elif protocol in ('http', 'ws'):
            port = 80
        elif protocol == 'ntp':
            port = 123
    
    # Determine if secure
    secure = protocol in ('https', 'wss')
    
    return URI(host, port, path, secure, protocol)

class HttpRequest:
    """
    Memory-efficient HTTP request helper that pre-allocates headers.
    Reduces memory fragmentation by caching encoded strings.
    """

    def __init__(self, url, headers=None):
        """
        Initialize HTTP request helper.

        Args:
            url (str): The URL to request
            headers (dict, optional): Additional headers as key-value pairs
        """
        self.uri = parse_url(url)

        # Pre-allocate commonly used header strings to reduce allocations
        self._path_bytes = self.uri.path.encode('utf-8')
        self._hostname_bytes = self.uri.hostname.encode('utf-8')
        self._get_line = b'GET %s HTTP/1.0\r\n' % self._path_bytes
        self._host_header = b'Host: %s\r\n' % self._hostname_bytes
        self._crlf = b'\r\n'

        # Pre-encode additional headers if provided
        self._extra_headers = []
        if headers:
            for key, value in headers.items():
                header_line = b'%s: %s\r\n' % (key.encode('utf-8'), value.encode('utf-8'))
                self._extra_headers.append(header_line)

    async def get(self):
        """
        Perform HTTP GET request and return (reader, writer) tuple.
        Caller is responsible for closing the writer.

        Returns:
            tuple: (reader, writer) from asyncio.open_connection

        Raises:
            Exception: If status code is not 200
        """
        import asyncio

        reader, writer = await asyncio.open_connection(
            self.uri.hostname,
            self.uri.port,
            ssl=self.uri.secure
        )

        try:
            # Write pre-allocated headers
            writer.write(self._get_line)
            writer.write(self._host_header)
            for header in self._extra_headers:
                writer.write(header)
            writer.write(self._crlf)
            await writer.drain()

            # Read and check status
            line = await reader.readline()
            status = line.split(b' ', 2)
            status_code = int(status[1])

            if status_code != 200:
                raise Exception(f"HTTP {status_code}")

            # Skip headers until blank line
            while True:
                line = await reader.readline()
                if line == b'\r\n':
                    break
            
            return reader, writer
        
        except Exception:
            writer.close()
            await writer.wait_closed()
            raise

    def get_scoped(self):
        """
        Returns an async context manager that automatically closes the connection.
        
        Usage:
            async with http_request.get_scoped() as (reader, writer):
                ...
        """
        return ScopedConnection(self.get)


async def stream_reader_to_buffer(reader, framebuffer):
    """
    Stream data from a reader directly into a framebuffer.

    Args:
        reader: The async reader to read from
        framebuffer (memoryview): The framebuffer to stream data into

    Returns:
        int: Number of bytes read
    """
    bytes_read = 0
    if hasattr(reader, 'readinto'):
        # MicroPython - keep reading chunks until no more data
        while bytes_read < len(framebuffer):
            remaining_buffer = framebuffer[bytes_read:]
            chunk_bytes = await reader.readinto(remaining_buffer)
            if chunk_bytes is None or chunk_bytes == 0:
                break
            bytes_read += chunk_bytes
    else:
        # CPython - keep reading until no more data
        while bytes_read < len(framebuffer):
            chunk = await reader.read(len(framebuffer) - bytes_read)
            if not chunk:
                break
            chunk_len = len(chunk)
            framebuffer[bytes_read:bytes_read + chunk_len] = chunk
            bytes_read += chunk_len
    return bytes_read


class ScopedConnection:
    def __init__(self, connect_func):
        self.connect_func = connect_func
        self.writer = None

    async def __aenter__(self):
        self.reader, self.writer = await self.connect_func()
        return self.reader, self.writer

    async def __aexit__(self, exc_type, exc, tb):
        if self.writer:
            self.writer.close()
            await self.writer.wait_closed()


