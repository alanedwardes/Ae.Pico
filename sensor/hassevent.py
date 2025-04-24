import time
import asyncio
import machine

class HassEvent:
    def __init__(self, hass, pin, event_type):
        self.hass = hass
        self.pin = machine.Pin(pin, machine.Pin.IN, machine.Pin.PULL_DOWN)
        self.pin.irq(self.interrupt)
        self.event_type = event_type
        self.tsf = asyncio.ThreadSafeFlag()

    def interrupt(self, pin):
        if pin.value() == 1:
            self.tsf.set()

    CREATION_PRIORITY = 1
    def create(provider):
        config = provider['config']['event']
        return HassEvent(provider['hass.Hass'], config['pin'], config['event_type'])
    
    async def start(self):
        last_change = time.ticks_ms()
        while True:
            await self.tsf.wait()
            await self.hass.post_event(self.event_type, dict(ms_since_last_event=time.ticks_diff(time.ticks_ms(), last_change)))
            last_change = time.ticks_ms()
