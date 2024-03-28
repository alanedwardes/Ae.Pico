import _thread
import utime
import machine

class Watchdog:
    timeout = None
    last_updated_time = None
    thread = None
    
    def __init__(self, timeout = 30_000):
        self.timeout = timeout
        self.last_updated_time = utime.ticks_ms()
        self.thread = _thread.start_new_thread(self.__watchdog, ())
        
    def feed(self):
        self.last_updated_time = utime.ticks_ms()
        
    def __watchdog(self):
        while True:
            time_since_last_update = utime.ticks_diff(utime.ticks_ms(), self.last_updated_time)
            if time_since_last_update > 30_000:
                print('Watchdog detected hang. Attempting reset (debugger will disconnect)')
                machine.reset()
            utime.sleep(1)
