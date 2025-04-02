import asyncio

class OccupancyBacklight:
    def __init__(self, hass, display, occupancy_entity_id):
        self.hass = hass
        self.display = display
        self.occupancy_entity_id = occupancy_entity_id

    CREATION_PRIORITY = 1
    def create(provider):
        config = provider['config']['display']
        return OccupancyBacklight(provider['hassws.HassWs'], provider['display'], config['occupancy_entity_id'])

    async def start(self):
        await self.hass.subscribe([self.occupancy_entity_id], self.occupancy_updated)
        await asyncio.Event().wait()

    def occupancy_updated(self, entity_id, entity):
        self.display.set_backlight(1 if entity['s'] == 'on' else 0)
