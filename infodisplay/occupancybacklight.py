import asyncio

class OccupancyBacklight:
    def __init__(self, hass, display, occupancy_entity_id):
        self.hass = hass
        self.display = display
        self.occupancy_entity_id = occupancy_entity_id
        self._current_backlight = 0.0
        self._fade_task = None

    CREATION_PRIORITY = 1
    def create(provider):
        config = provider['config']['display']
        return OccupancyBacklight(provider['hassws.HassWs'], provider['display'], config['occupancy_entity_id'])

    async def start(self):
        await self.hass.subscribe([self.occupancy_entity_id], self.occupancy_updated)
        await asyncio.Event().wait()

    def occupancy_updated(self, entity_id, entity):
        target = 1.0 if entity['s'] == 'on' else 0.0
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
            # Ensure we hit the exact target at the end
            self.display.set_backlight(target)
            self._current_backlight = target
        except asyncio.CancelledError:
            raise
