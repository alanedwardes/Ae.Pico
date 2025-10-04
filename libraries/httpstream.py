import re
from collections import namedtuple

# Support multiple protocols
URL_RE = re.compile(r'(http|https|ws|wss|ntp)://([A-Za-z0-9-\.]+)(?:\:([0-9]+))?(.+)?')
URI = namedtuple('URI', ('hostname', 'port', 'path', 'secure', 'protocol'))

def parse_url(url):
    """
    Parse a URL into its components.
    
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
    match = URL_RE.match(url)
    if match:
        protocol = match.group(1)
        host = match.group(2)
        port = match.group(3)
        path = match.group(4)

        # Set default ports based on protocol
        if port is None:
            if protocol in ('https', 'wss'):
                port = 443
            elif protocol in ('http', 'ws'):
                port = 80
            elif protocol == 'ntp':
                port = 123
            else:
                raise ValueError('Scheme {} is invalid'.format(protocol))

        # Determine if secure
        secure = protocol in ('https', 'wss')

        return URI(host, int(port), path if path else '/', secure, protocol)
    raise ValueError('Invalid URL format')

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

