import asyncio
import machine

class HassMotion:
    def __init__(self, hass, pin, friendly_name, sensor, timeout_seconds, debounce_ms):
        self.hass = hass
        self.pin = machine.Pin(pin, machine.Pin.IN)
        self.pin.irq(self.interrupt, machine.Pin.IRQ_RISING)
        self.friendly_name = friendly_name
        self.sensor = sensor
        self.timeout_seconds = timeout_seconds
        self.debounce_ms = debounce_ms
        self.tsf = asyncio.ThreadSafeFlag()

    def interrupt(self, pin):
        self.tsf.set()

    CREATION_PRIORITY = 1
    def create(provider):
        config = provider['config']['motion']
        return HassMotion(provider['hass.Hass'], config['pin'], config['friendly_name'], config['sensor'], config.get('timeout_seconds', 300), config.get('debounce_ms', 100))
    
    async def start(self):
        while True:
            try:
                await asyncio.wait_for(self.tsf.wait(), self.timeout_seconds)
                await asyncio.sleep_ms(self.debounce_ms)
                await self.hass.send_update("on" if self.pin.value() == 1 else "off", None, "motion", self.friendly_name, self.sensor)
            except asyncio.TimeoutError:
                await self.hass.send_update("off", None, "motion", self.friendly_name, self.sensor)
