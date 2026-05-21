import utime
import asyncio
import datetime as _dt

class LocalTime:
    CREATION_PRIORITY = 1

    def create(provider):
        if 'time' in provider:
            return None
        instance = LocalTime()
        provider['time'] = instance
        return instance

    def utc_offset_seconds(self):
        offset = _dt.datetime.now().astimezone().utcoffset()
        return int(offset.total_seconds())

    def local_time(self):
        return utime.localtime()

    async def start(self):
        await asyncio.Event().wait()
