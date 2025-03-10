import asyncio
from machine import WDT

class Watchdog:
    def __init__(self):
        self.wdt = WDT()
    
    def create(provider):
        return Watchdog()
    
    async def start(self):
        while True:
            self.wdt.feed()
            await asyncio.sleep(1)
