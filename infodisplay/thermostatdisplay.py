import gauge
import utime
import asyncio

class ThermostatDisplay:
    def __init__(self, display, hass, entity_id):
        self.display = display
        self.hass = hass
        self.entity_id = entity_id

        self.display_width, self.display_height = self.display.get_bounds()
        
        self.entities = dict()
        self.alpha = 0
    
    CREATION_PRIORITY = 1
    def create(provider):
        return ThermostatDisplay(provider['display'], provider['hassws.HassWs'], provider['config']['thermostat']['entity_id'])
    
    def entity_updated(self, entity_id, entity):
        self.entities[entity_id] = entity
        self.update()
    
    async def start(self):
        await self.hass.subscribe([self.entity_id], self.entity_updated)
        # For testing
        #while True:
        #    self.update()
        #    await asyncio.sleep(1)
        await asyncio.Event().wait()
        
    def update(self):
        start_update_ms = utime.ticks_ms()
        self.__update()
        update_time_ms = utime.ticks_diff(utime.ticks_ms(), start_update_ms)
        print(f"ThermostatDisplay: {update_time_ms}ms")

    def __update(self):
        default_entity = dict(s = '0')
        thermostat_entity = self.entities.get(self.entity_id, default_entity)
        minimum_temperature = float(thermostat_entity['a']['min_temp'])
        maximum_temperature = float(thermostat_entity['a']['max_temp'])
        current_target = float(thermostat_entity['a']['temperature'])
        current_temperature = float(thermostat_entity['a']['current_temperature'])
        
        self.display.set_pen(self.display.create_pen(0, 0, 0))
        self.display.rectangle(0, 70, self.display_width, self.display_height - 70)
        
        gauge.draw_gauge(self.display, (0, 80), (self.display_width / 2, self.display_height - 100), minimum_temperature, maximum_temperature, current_target)
        
        self.display.set_thickness(5)
        self.display.set_font("sans")
        self.display.text(thermostat_entity['a']['hvac_action'], int(self.display_width / 2), 120, scale=2)
        self.display.text(f"{current_temperature:.0f}c", int(self.display_width / 2), 200, scale=2)
        
        self.display.update()
