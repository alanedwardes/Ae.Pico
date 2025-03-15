import utime
import asyncio

class Ticker:
    def create(provider):
        return Ticker()
    
    async def start(self):
        # Compare an expected sleep ms
        # with actual sleep to ensure
        # async loop is not blocked
        expected_sleep_ms = 100
        error_margin_ms = 20
        
        while True:
            start = utime.ticks_ms()
            await asyncio.sleep_ms(expected_sleep_ms)
            actual_sleep_ms = utime.ticks_diff(utime.ticks_ms(), start)
            if actual_sleep_ms > expected_sleep_ms + error_margin_ms:
                print("WARNING: Async loop delayed by %ims" % (actual_sleep_ms - expected_sleep_ms))
