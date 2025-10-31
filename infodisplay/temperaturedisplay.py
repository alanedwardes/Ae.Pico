import gauge
import utime
import asyncio

class TemperatureDisplay:
    def __init__(self, display, hass, entity_ids):
        self.display = display
        self.hass = hass
        self.entity_ids = entity_ids

        self.display_width, self.display_height = self.display.get_bounds()
        
        self.alpha = 0
    
    CREATION_PRIORITY = 1
    def create(provider):
        return TemperatureDisplay(provider['display'], provider['hassws.HassWs'], provider['config']['temperature'])
    
    def entity_updated(self, entity_id, entity):
        self.update()
    
    async def start(self):
        await self.hass.subscribe(self.entity_ids.values(), self.entity_updated)
        # For testing
        #while True:
        #    self.update()
        #    await asyncio.sleep(1)
        await asyncio.Event().wait()
        
    def update(self):
        start_update_ms = utime.ticks_ms()
        self.__update()
        update_time_ms = utime.ticks_diff(utime.ticks_ms(), start_update_ms)
        print(f"TemperatureDisplay: {update_time_ms}ms")

    def __update(self):
        default_entity = dict(s = '0')
        minimum_temperature = float(self.hass.entities.get(self.entity_ids['minimum_temp_entity_id'], default_entity)['s'])
        maximum_temperature = float(self.hass.entities.get(self.entity_ids['maximum_temp_entity_id'], default_entity)['s'])
        current_temperature = float(self.hass.entities.get(self.entity_ids['current_temp_entity_id'], default_entity)['s'])
        
        self.display.set_pen(self.display.create_pen(0, 0, 0))
        self.display.rect(self.display_width - 64, 0, 64, 70, self.display.create_pen(0, 0, 0), True)
        
        gauge.draw_gauge(self.display, (self.display_width - 64, 0), (64, 64), minimum_temperature, maximum_temperature, current_temperature)
        self.display.update()
