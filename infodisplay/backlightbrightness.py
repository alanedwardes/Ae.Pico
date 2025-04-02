import asyncio

class BacklightBrightness:
    def __init__(self, hass, display, brightness_entity_id):
        self.hass = hass
        self.display = display
        self.brightness_entity_id = brightness_entity_id

    CREATION_PRIORITY = 1
    def create(provider):
        config = provider['config']['display']
        return BacklightBrightness(provider['hassws.HassWs'], provider['display'], config['brightness_entity_id'])

    async def start(self):
        await self.hass.subscribe([self.brightness_entity_id], self.brightness_updated)
        await asyncio.Event().wait()

    def brightness_updated(self, entity_id, entity):
        self.display.set_backlight(float(entity['s'])/100)
