import re
import asyncio
from collections import namedtuple

URL_RE = re.compile(r'(http|https)://([A-Za-z0-9-\.]+)(?:\:([0-9]+))?(.+)?')
URI = namedtuple('URI', ('hostname', 'port', 'path'))

def urlparse(uri):
    match = URL_RE.match(uri)
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

        return URI(host.encode('ascii'), int(port), path.encode('utf-8'))

class RemoteTime:
    def __init__(self, endpoint, update_time_ms, nic):
        self.uri = urlparse(endpoint)
        self.update_time_ms = update_time_ms
        self.nic = nic
    
    async def start(self):
        while not self.nic.isconnected():
            await asyncio.sleep_ms(100)
        
        while True:
            await self.update_time()
            await asyncio.sleep_ms(self.update_time_ms)
    
    async def stop(self):
        pass

    async def get_time(self):
        reader, writer = await asyncio.open_connection(self.uri.hostname, self.uri.port, ssl = self.uri.port == 443)
        writer.write(b'GET %s HTTP/1.0\r\nHost: %s\r\n\r\n' % (self.uri.path, self.uri.hostname))
        await writer.drain()
        
        lastline = None
        while True:
            line = await reader.readline()
            if not line:
                break
            lastline = line
        
        writer.close()
        await writer.wait_closed()
        return tuple(map(int, lastline.split(b',')))
    
    async def update_time(self):
        ts = await self.get_time()
        import machine
        machine.RTC().datetime(ts)
