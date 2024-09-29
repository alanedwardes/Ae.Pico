try:
    import urequests
except ModuleNotFoundError:
    import requests as urequests

import utime

class RemoteTime:
    def __init__(self, tz, update_time_ms):
        self.tz = tz
        self.update_time_ms = update_time_ms
        self.last_updated_time = None
    
    def update(self):
        if self.last_updated_time is None or utime.ticks_diff(utime.ticks_ms(), self.last_updated_time) > self.update_time_ms:
            try:
                self.update_time()
                self.last_updated_time = utime.ticks_ms()
            except Exception as e:
                print(e)

    def get_time(self):
        response = urequests.get("http://time.alanedwardes.com/?tz=%s&fmt=%%Y,%%m,%%d,%%w,%%H,%%M,%%S,%%f" % self.tz)

        if not response.status_code == 200:
            raise Exception("Status " + str(response.status_code) + ": " + response.text)
        
        return tuple(map(int, response.text.split(',')))
    
    def update_time(self):
        ts = self.get_time()
        import machine
        machine.RTC().datetime(ts)
