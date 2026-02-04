import asyncio
import utime

class AsyncDiagnostics:
    def __init__(self, threshold_ms=100):
        self.threshold_ms = threshold_ms
    
    def create(provider):
        config = provider.get('config', {}).get('diagnostics', {})
        return AsyncDiagnostics(config.get('hitch_threshold_ms', 100))
    
    async def start(self):
        print("AsyncDiagnostics started")
        while True:
            t0 = utime.ticks_ms()
            await asyncio.sleep(0)
            t1 = utime.ticks_ms()
            
            delta = utime.ticks_diff(t1, t0)
            if delta > self.threshold_ms:
                print(f"Async hitch detected: {delta}ms")
            
            # Sleep for half the threshold to allow other tasks to run
            await asyncio.sleep(self.threshold_ms / 2000)
