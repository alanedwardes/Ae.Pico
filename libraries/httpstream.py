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

