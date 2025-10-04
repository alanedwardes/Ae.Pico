import utime
import struct
import socket
import asyncio
from httpstream import parse_url

class RemoteTime:
    def __init__(self, endpoint, update_time_ms, nic):
        self.uri = parse_url(endpoint)
        self.update_time_ms = update_time_ms
        self.nic = nic
        
        tm = utime.gmtime(0)
        self.last_update = utime.ticks_ms()
        self.last_timestamp = (tm[0], tm[1], tm[2], tm[6] + 1, tm[3], tm[4], tm[5], 0)

    def create(provider):
        config = provider['config']['remotetime']
        return RemoteTime(config['endpoint'], config['update_time_ms'], provider['nic'])

    async def start(self):
        while not self.nic.isconnected():
            await asyncio.sleep_ms(100)
        
        while True:
            await self.update_time()
            await asyncio.sleep_ms(self.update_time_ms)

    async def acquire_time(self):
        NTP_QUERY = bytearray(48)
        NTP_QUERY[0] = 0x1B
        addr = socket.getaddrinfo(self.uri.hostname, self.uri.port)[0][-1]
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        receive_milliseconds = 0
        try:
            s.settimeout(1)
            s.sendto(NTP_QUERY, addr)
            sent_time = utime.ticks_ms()
            msg = s.recv(48)
            # Time how long it takes to obtain a response and adjust
            receive_milliseconds = utime.ticks_diff(utime.ticks_ms(), sent_time)
        finally:
            s.close()
        val = struct.unpack("!I", msg[40:44])[0]
        val2 = struct.unpack("!I", msg[44:48])[0]

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
        
        adjust_seconds = receive_milliseconds // 1000
        adjust_milliseconds = receive_milliseconds % 1000
        
        milliseconds = (val2 * 1000) // 0x100000000
        
        tm = utime.gmtime(t)
        return (tm[0], tm[1], tm[2], tm[6] + 1, tm[3], tm[4], tm[5] + adjust_seconds, milliseconds + adjust_milliseconds)
    
    # Provides a method compatible with machine.RTC to obtain the time
    # Provides millisecond resolution (whereas on some ports machine.RTC does not)
    def datetime(self):
        total_milliseconds = self.last_timestamp[7] + utime.ticks_diff(utime.ticks_ms(), self.last_update)       
        total_seconds = self.last_timestamp[6] + (total_milliseconds // 1000)
        total_minutes = self.last_timestamp[5] + (total_seconds // 60)
        total_hours = self.last_timestamp[4] + (total_minutes // 60)
        
        milliseconds = total_milliseconds % 1000
        seconds = total_seconds % 60
        minutes = total_minutes % 60
        hours = total_hours % 24
        
        # (year, month, day, weekday, hours, minutes, seconds, subseconds)
        return (self.last_timestamp[0], self.last_timestamp[1], self.last_timestamp[2], self.last_timestamp[3], hours, minutes, seconds, milliseconds)
    
    async def update_time(self):
        self.last_timestamp = await self.acquire_time()
        self.last_update = utime.ticks_ms()
        import machine
        machine.RTC().datetime(self.last_timestamp)
