import asyncio
import machine

class HassMotionRp2350:
    """
    RP2350 erratum: input+pull-down leaves pads leaky and they can float to ~2.2 V,
    latching a false high that the weak pull-down can't clear. To avoid parking
    in that state, we keep the pad as output-low between polls and only sample
    briefly as input with pull-down. Polling at ~50 ms is sufficient for PIRs
    (their highs are hundreds of ms) and avoids relying on potentially flaky IRQs.
    """
    def __init__(self, hass, pin, friendly_name, sensor, timeout_seconds, debounce_ms):
        self.hass = hass
        self.pin_number = pin
        self.friendly_name = friendly_name
        self.sensor = sensor
        self.timeout_seconds = timeout_seconds
        self.debounce_ms = debounce_ms
        self.last_reported_state = None
        # Start with the pin driven low to collapse any leakage condition per RP2350 erratum.
        self._disarm_pin()

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
            # Sample as input with pull-down, then go back to output-low to avoid leakage latch.
            self.pin = machine.Pin(self.pin_number, machine.Pin.IN, machine.Pin.PULL_DOWN)
            value = self.pin.value()
            state = "on" if value == 1 else "off"
            if state != self.last_reported_state:
                await self.hass.send_update(state, None, "motion", self.friendly_name, self.sensor)
                self.last_reported_state = state
            self._disarm_pin()
            await asyncio.sleep_ms(50)
