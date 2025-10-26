import utime
import struct
import socket
import asyncio
from httpstream import parse_url

class RemoteTime:
    def __init__(self, endpoint, update_time_ms, nic, offset_seconds=0, dst_delegate=None):
        self.uri = parse_url(endpoint)
        self.update_time_ms = update_time_ms
        self.nic = nic
        self.offset_seconds = offset_seconds
        self.dst_delegate = dst_delegate
        
        self.last_update = utime.ticks_ms()
        self.last_timestamp = 0.0

    def create(provider):
        config = provider['config']['remotetime']
        tz = config.get('timezone', {})

        return RemoteTime(
            config['endpoint'],
            config['update_time_ms'],
            provider.get('nic'),
            tz.get('offset_seconds', 0),
            tz.get('dst_delegate')
        )

    async def start(self):
        while self.nic and not self.nic.isconnected():
            await asyncio.sleep(0.1)
        
        while True:
            await self.update_time()
            await asyncio.sleep(self.update_time_ms / 1000)

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

        latency_adjust_seconds = receive_milliseconds / 1000.0
        fractional_ms = (val2 * 1000) // 0x100000000

        return t + (fractional_ms / 1000.0) + latency_adjust_seconds
    
    # Provides a method compatible with machine.RTC to obtain the time
    # Provides millisecond resolution (whereas on some ports machine.RTC does not)
    def datetime(self):
        elapsed_ms = utime.ticks_diff(utime.ticks_ms(), self.last_update)
        ts = self.last_timestamp + (elapsed_ms / 1000.0)
        seconds_utc = int(ts)
        milliseconds = int((ts - seconds_utc) * 1000)
        dst_offset = self.dst_delegate(seconds_utc) if self.dst_delegate else 0
        local_seconds = seconds_utc + self.offset_seconds + dst_offset
        tm = utime.gmtime(local_seconds)
        # (year, month, day, weekday, hours, minutes, seconds, subseconds)
        return (tm[0], tm[1], tm[2], tm[6] + 1, tm[3], tm[4], tm[5], milliseconds)
    
    async def update_time(self):
        self.last_timestamp = await self.acquire_time()
        self.last_update = utime.ticks_ms()
        seconds = int(self.last_timestamp)
        milliseconds = int((self.last_timestamp - seconds) * 1000)
        tm = utime.gmtime(seconds)
        rtc_tuple = (tm[0], tm[1], tm[2], tm[6] + 1, tm[3], tm[4], tm[5], milliseconds)
        import machine
        machine.RTC().datetime(rtc_tuple)

def _is_leap(y):
    return (y % 4 == 0 and (y % 100 != 0 or y % 400 == 0))

def _month_days(y):
    return (31, 29 if _is_leap(y) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)

def last_sunday(year, month):
    last_day = _month_days(year)[month - 1]
    ts = utime.mktime((year, month, last_day, 0, 0, 0, 0, 0))
    wd_last = utime.gmtime(ts)[6]
    delta = (wd_last - 6) % 7
    return last_day - delta

def eu_uk_daylight_savings_offset_seconds(utc_seconds):
    tm = utime.gmtime(utc_seconds)
    year = tm[0]
    start_day = last_sunday(year, 3)
    start_utc = utime.mktime((year, 3, start_day, 1, 0, 0, 0, 0))
    end_day = last_sunday(year, 10)
    end_utc = utime.mktime((year, 10, end_day, 1, 0, 0, 0, 0))
    return 3600 if (utc_seconds >= start_utc and utc_seconds < end_utc) else 0
