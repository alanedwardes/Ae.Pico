import time
import asyncio
import machine

class HassEvent:
    def __init__(self, hass, pin, event_type, debounce_ms):
        self.hass = hass
        self.pin = machine.Pin(pin, machine.Pin.IN, machine.Pin.PULL_DOWN)
        self.pin.irq(self.interrupt, machine.Pin.IRQ_RISING)
        self.event_type = event_type
        self.debounce_ms = debounce_ms
        self.tsf = asyncio.ThreadSafeFlag()

    def interrupt(self, pin):
        self.tsf.set()

    CREATION_PRIORITY = 1
    def create(provider):
        config = provider['config']['event']
        return HassEvent(provider['hass.Hass'], config['pin'], config['event_type'], config.get('debounce_ms', 100))
    
    async def start(self):
        while True:
            await self.tsf.wait()
            await asyncio.sleep_ms(self.debounce_ms)

            if self.pin.value() == 1:
                await self.hass.post_event(self.event_type, dict())
