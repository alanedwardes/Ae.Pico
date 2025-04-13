import asyncio
import machine

class HassMotion:
    def __init__(self, hass, pin, friendly_name, sensor, timeout_seconds):
        self.hass = hass
        self.pin = machine.Pin(pin, machine.Pin.IN, machine.Pin.PULL_DOWN)
        self.pin.irq(self.interrupt, machine.Pin.IRQ_RISING)
        self.friendly_name = friendly_name
        self.sensor = sensor
        self.timeout_seconds = timeout_seconds
        self.tsf = asyncio.ThreadSafeFlag()

    def interrupt(self, pin):
        self.tsf.set()

    CREATION_PRIORITY = 1
    def create(provider):
        config = provider['config']['motion']
        return HassMotion(provider['hass.Hass'], config['pin'], config['friendly_name'], config['sensor'], config.get('timeout_seconds', 300))
    
    async def start(self):
        while True:
            # Wait for initial motion signal
            await self.tsf.wait()
            await self.hass.send_update("on", None, "motion", self.friendly_name, self.sensor)
            
            # Once motion has been detected
            try:
                while True:
                    # Wait for either another signal, or a timeout
                    await asyncio.wait_for(self.tsf.wait(), self.timeout_seconds)
            except asyncio.TimeoutError:
                # The timer elapsed without detection so signal no motion
                await self.hass.send_update("off", None, "motion", self.friendly_name, self.sensor)
