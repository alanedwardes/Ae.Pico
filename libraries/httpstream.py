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

