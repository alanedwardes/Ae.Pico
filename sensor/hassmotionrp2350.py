import asyncio
import machine

class HassMotionRp2350:
    """
    RP2350 erratum: input+pull-down leaves pads leaky and can float to ~2.2 V,
    latching a false high that the weak pull-down can't clear. To avoid parking
    in that state, we keep the pad as output-low between waits and only enable
    input+IRQ during the armed window. After handling (or timeout) we drop the
    IRQ and drive low again to collapse any leakage. This greatly reduces false
    highs; only sub-millisecond pulses entirely within the brief disarm window
    could be missed, which is acceptable for typical PIR sensors (hundreds of
    ms high).
    """
    def __init__(self, hass, pin, friendly_name, sensor, timeout_seconds, debounce_ms):
        self.hass = hass
        self.pin_number = pin
        self.friendly_name = friendly_name
        self.sensor = sensor
        self.timeout_seconds = timeout_seconds
        self.debounce_ms = debounce_ms
        self.tsf = asyncio.ThreadSafeFlag()
        # Start with the pin driven low to collapse any leakage condition per RP2350 erratum.
        self._disarm_pin()

    def interrupt(self, pin):
        self.tsf.set()

    def _setup_pin(self):
        self.pin = machine.Pin(self.pin_number, machine.Pin.IN, machine.Pin.PULL_DOWN)
        self.pin.irq(self.interrupt, machine.Pin.IRQ_RISING)

    def _disarm_pin(self):
        # Drive low as output so the pad is held below the undefined region; avoids leakage latch.
        self.pin = machine.Pin(self.pin_number, machine.Pin.OUT, value=0)

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
            # Arm: input with pull-down + rising IRQ
            self._setup_pin()
            try:
                await asyncio.wait_for(self.tsf.wait(), self.timeout_seconds)
                await asyncio.sleep_ms(self.debounce_ms)
                value = self.pin.value()
                state = "on" if value == 1 else "off"
                await self.hass.send_update(state, None, "motion", self.friendly_name, self.sensor)
            except asyncio.TimeoutError:
                await self.hass.send_update("off", None, "motion", self.friendly_name, self.sensor)
            finally:
                # Disarm: drop IRQ and drive low to clear leakage-prone state before re-arming.
                try:
                    self.pin.irq(handler=None)
                except Exception:
                    pass
                self._disarm_pin()

