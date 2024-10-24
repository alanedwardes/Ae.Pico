import re
import utime
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

        return URI(host.encode('ascii'), int(port), b'/' if path is None else path.encode('utf-8'))

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

    async def update_time(self):
        reader, writer = await asyncio.open_connection(self.uri.hostname, self.uri.port, ssl = self.uri.port == 443)

        # Request the time
        writer.write(b'GET %s HTTP/1.0\r\nHost: %s\r\n\r\n' % (self.uri.path, self.uri.hostname))
        await writer.drain()

        # Now we sent the request, start the clock
        started_time = utime.ticks_ms()

        # Grab the entire response
        buffer = await reader.read(2048)

        # Parse the epoch header out e.g. "e: 1729723167.03642"
        time_seconds = float(buffer.split(b'\r\ne: ', 1)[1].split(b'\r\n', 1)[0])

        # Stop the clock
        time_taken_seconds = float(utime.ticks_diff(utime.ticks_ms(), started_time)) / 1000

        # Adjust the epoch and process it
        tm = utime.gmtime(int(time_seconds - time_taken_seconds))

        # Create the tuple to pass to the RTC
        tp = (tm[0], tm[1], tm[2], tm[6] + 1, tm[3], tm[4], tm[5], 0)
        
        # Set the time
        import machine
        machine.RTC().datetime(tp)

        # Clean up
        writer.close()
        await writer.wait_closed()

        return tp
