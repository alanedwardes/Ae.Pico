import re
import utime
import struct
import socket
import asyncio
from collections import namedtuple

URL_RE = re.compile(r'ntp://([A-Za-z0-9-\.]+)(?:\:([0-9]+))?(.+)?')
URI = namedtuple('URI', ('hostname', 'port', 'path'))

def urlparse(uri):
    match = URL_RE.match(uri)
    if match:
        host = match.group(1)
        port = match.group(2)
        path = match.group(3)

        if port is None:
            port = 123

        return URI(host.encode('ascii'), int(port), b'/' if path is None else path.encode('utf-8'))

class RemoteTime:
    def __init__(self, endpoint, update_time_ms, nic):
        self.uri = urlparse(endpoint)
        self.update_time_ms = update_time_ms
        self.nic = nic

    def create(provider):
        config = provider['config'].clock
        return RemoteTime(config['endpoint'], config['update_time_ms'], provider['nic'])

    async def start(self):
        while not self.nic.isconnected():
            await asyncio.sleep_ms(100)
        
        while True:
            await self.update_time()
            await asyncio.sleep_ms(self.update_time_ms)
    
    async def stop(self):
        pass

    async def get_time(self):
        NTP_QUERY = bytearray(48)
        NTP_QUERY[0] = 0x1B
        addr = socket.getaddrinfo(self.uri.hostname, self.uri.port)[0][-1]
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.settimeout(1)
            s.sendto(NTP_QUERY, addr)
            msg = s.recv(48)
        finally:
            s.close()
        val = struct.unpack("!I", msg[40:44])[0]

        MIN_NTP_TIMESTAMP = 3913056000

        if val < MIN_NTP_TIMESTAMP:
            val += 0x100000000

        EPOCH_YEAR = utime.gmtime(0)[0]
        if EPOCH_YEAR == 2000:
            NTP_DELTA = 3155673600
        elif EPOCH_YEAR == 1970:
            NTP_DELTA = 2208988800
        else:
            raise Exception("Unsupported epoch: {}".format(EPOCH_YEAR))

        t = val - NTP_DELTA
        tm = utime.gmtime(t)
        return (tm[0], tm[1], tm[2], tm[6] + 1, tm[3], tm[4], tm[5], 0)
    
    async def update_time(self):
        ts = await self.get_time()
        import machine
        machine.RTC().datetime(ts)
