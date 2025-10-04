import re
from collections import namedtuple

URL_RE = re.compile(r'(http|https)://([A-Za-z0-9-\.]+)(?:\:([0-9]+))?(.+)?')
URI = namedtuple('URI', ('hostname', 'port', 'path', 'secure'))

def parse_url(url):
    """
    Parse a URL into its components.
    
    Args:
        url (str): The URL to parse
        
    Returns:
        URI: Named tuple with (hostname, port, path, secure) where:
            - hostname (str): The hostname
            - port (int): The port number
            - path (str): The path (defaults to '/' if None)
            - secure (bool): True if HTTPS, False if HTTP
            
    Raises:
        ValueError: If the URL format is invalid or scheme is not http/https
    """
    match = URL_RE.match(url)
    if match:
        protocol = match.group(1)
        host = match.group(2)
        port = match.group(3)
        path = match.group(4)

        if protocol == 'https':
            if port is None:
                port = 443
        elif protocol == 'http':
            if port is None:
                port = 80
        else:
            raise ValueError('Scheme {} is invalid'.format(protocol))

        return URI(host, int(port), path if path else '/', protocol == 'https')
    raise ValueError('Invalid URL format')
