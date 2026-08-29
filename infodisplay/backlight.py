import asyncio

class Backlight:
    def __init__(self, display, hass, event_bus, brightness_entity_id):
        self.display = display
        self.hass = hass
        self.event_bus = event_bus
        self.brightness_entity_id = brightness_entity_id
        self._awake = True
        self._target_brightness = 1.0
        self._current_backlight = 0.0
        self._fade_task = None

    CREATION_PRIORITY = 1
    def create(provider):
        config = provider['config']['display']
        return Backlight(
            provider['display'],
            provider['hassws.HassWs'],
            provider['eventbus.EventBus'],
            config.get('brightness_entity_id'),
        )

    async def start(self):
        if self.brightness_entity_id:
            await self.hass.subscribe([self.brightness_entity_id], self._brightness_updated)
        self.event_bus.subscribe('system.sleep', self._on_sleep)
        self.event_bus.subscribe('system.wake', self._on_wake)
        self._set_fade_target(self._target_brightness if self._awake else 0.0)
        await asyncio.Event().wait()

    def _brightness_updated(self, entity_id, entity):
        self._target_brightness = float(entity['s'])
        if self._awake:
            self._set_fade_target(self._target_brightness)

    def _on_sleep(self, ev):
        self._awake = False
        self._set_fade_target(0.0)

    def _on_wake(self, ev):
        self._awake = True
        self._set_fade_target(self._target_brightness)

    def _set_fade_target(self, target):
        if self._fade_task is not None and not self._fade_task.done():
            self._fade_task.cancel()
        self._fade_task = asyncio.create_task(self._fade_to(target))

    async def _fade_to(self, target, duration=0.5, steps=50):
        start = self._current_backlight
        diff = target - start
        if diff == 0:
            return

        try:
            for i in range(1, steps + 1):
                new_val = start + (diff * i / steps)
                self.display.set_backlight(new_val)
                self._current_backlight = new_val
                await asyncio.sleep(duration / steps)
            self.display.set_backlight(target)
            self._current_backlight = target
        except asyncio.CancelledError:
            raise
