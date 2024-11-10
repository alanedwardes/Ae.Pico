import re
import utime
import struct
import socket
import asyncio
import binascii
from collections import namedtuple

URL_RE = re.compile(r'(ntp|http|https)://([A-Za-z0-9-\.]+)(?:\:([0-9]+))?(.+)?')
URI = namedtuple('URI', ('protocol', 'hostname', 'port', 'path'))

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
        elif protocol == 'ntp':
            if port is None:
                port = 123
            pass
        else:
            raise ValueError('Scheme {} is invalid'.format(protocol))

        return URI(protocol, host.encode('ascii'), int(port), b'/' if path is None else path.encode('utf-8'))

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
        if self.uri.protocol == 'ntp':
            return await self.get_time_ntp()
        elif self.uri.protocol == 'http' or self.uri.protocol == 'https':
            return await self.get_time_http()

    async def get_time_ntp(self):
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

    async def get_time_http(self):
        reader, writer = await asyncio.open_connection(self.uri.hostname, self.uri.port, ssl = self.uri.port == 443)
        writer.write(b'GET %s HTTP/1.0\r\nHost: %s\r\n\r\n' % (self.uri.path, self.uri.hostname))
        await writer.drain()

        header_prefix = b'Hora: '
        
        while True:
            line = await reader.readline()
            if not line:
                raise Exception('Time header not found in response')

            if line.startswith(header_prefix):
                writer.close()
                await writer.wait_closed()
                return struct.unpack('HBBBBBBH', binascii.unhexlify(line[len(header_prefix):-2]))
    
    async def update_time(self):
        ts = await self.get_time()
        import machine
        machine.RTC().datetime(ts)
