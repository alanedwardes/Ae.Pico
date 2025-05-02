import utime
import asyncio
import machine

class HassMotionFrequency:
    def __init__(self, hass, pin, friendly_name, sensor, timeout_seconds, debounce_ms):
        self.hass = hass
        self.pin = machine.Pin(pin, machine.Pin.IN, machine.Pin.PULL_DOWN)
        self.pin.irq(self.interrupt, machine.Pin.IRQ_RISING)
        self.friendly_name = friendly_name
        self.sensor = sensor
        self.timeout_seconds = timeout_seconds
        self.debounce_ms = debounce_ms
        self.tsf = asyncio.ThreadSafeFlag()
        self.timestamps = set()
        self.last_updated_state = None

    def interrupt(self, pin):
        self.tsf.set()

    CREATION_PRIORITY = 1
    def create(provider):
        config = provider['config']['motion']
        return HassMotionFrequency(provider['hass.Hass'], config['pin'], config['friendly_name'], config['sensor'], config.get('timeout_seconds', 300), config.get('debounce_ms', 100))
    
    def expire_timestamps(self):
        expired_timestamps = {timestamp for timestamp in self.timestamps if utime.ticks_diff(utime.ticks_ms(), timestamp) > self.timeout_seconds * 1000}
        self.timestamps -= expired_timestamps
        return len(expired_timestamps)
    
    async def send_update(self):
        new_state = len(self.timestamps)
        
        if new_state != self.last_updated_state:
            await self.hass.post_state(self.sensor, {"state": new_state, "attributes": {"friendly_name": self.friendly_name, "state_class": "measurement"}})
            self.last_updated_state = new_state
        
    async def tidy_loop(self):
        while True:
            await asyncio.sleep(1)
            self.expire_timestamps()
            await self.send_update()
            
    async def motion_loop(self):
        while True:
            await self.tsf.wait()
            await asyncio.sleep_ms(self.debounce_ms)
            
            if self.pin.value() == 1:
                self.timestamps.add(utime.ticks_ms())
                await self.send_update()
    
    async def start(self):
        await asyncio.gather(self.tidy_loop(), self.motion_loop())
