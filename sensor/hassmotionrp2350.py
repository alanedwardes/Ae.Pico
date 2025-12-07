import asyncio
import machine

class HassMotionRp2350:
    def __init__(self, hass, pin, friendly_name, sensor, timeout_seconds, debounce_ms):
        self.hass = hass
        self.pin_number = pin
        self._setup_pin()
        self.friendly_name = friendly_name
        self.sensor = sensor
        self.timeout_seconds = timeout_seconds
        self.debounce_ms = debounce_ms
        self.tsf = asyncio.ThreadSafeFlag()

    def interrupt(self, pin):
        self.tsf.set()

    def _setup_pin(self):
        self.pin = machine.Pin(self.pin_number, machine.Pin.IN)
        self.pin.irq(self.interrupt, machine.Pin.IRQ_RISING)

    def reset_pin(self):
        # Clear the latched high by briefly driving the pin low, then restoring the input/IRQ setup.
        self.pin = machine.Pin(self.pin_number, machine.Pin.OUT, value=0)
        self._setup_pin()

    CREATION_PRIORITY = 1
    def create(provider):
        config = provider["config"]["motion"]
        return HassMotionRp2350(
            provider["hass.Hass"],
            config["pin"],
            config["friendly_name"],
            config["sensor"],
            config.get("timeout_seconds", 300),
            config.get("debounce_ms", 100),
        )

    async def start(self):
        while True:
            try:
                await asyncio.wait_for(self.tsf.wait(), self.timeout_seconds)
                await asyncio.sleep_ms(self.debounce_ms)
                value = self.pin.value()
                state = "on" if value == 1 else "off"
                if value == 1:
                    self.reset_pin()
                await self.hass.send_update(state, None, "motion", self.friendly_name, self.sensor)
            except asyncio.TimeoutError:
                await self.hass.send_update("off", None, "motion", self.friendly_name, self.sensor)

