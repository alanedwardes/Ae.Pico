import asyncio
from machine import Pin

class ThermostatButtons:
    def __init__(self, hass, thermostat_entity_id, default_max_temp = None):
        self.hass = hass
        self.thermostat_entity_id = thermostat_entity_id
        self.default_max_temp = default_max_temp
        self.debounce_ms = 250
        self.polling_rate_ms = 10
        self.a = Pin(12, Pin.IN, Pin.PULL_UP)
        self.b = Pin(13, Pin.IN, Pin.PULL_UP)
        self.x = Pin(14, Pin.IN, Pin.PULL_UP)
        self.y = Pin(15, Pin.IN, Pin.PULL_UP)
    
    CREATION_PRIORITY = 1
    def create(provider):
        thermostat_config = provider['config']['thermostat']
        return ThermostatButtons(
            provider['hassws.HassWs'],
            thermostat_config['entity_id'],
            thermostat_config.get('default_max_temp')
        )
    
    async def start(self):
        while True:
            for pin in [self.a, self.b, self.x, self.y]:
                if pin.value() == 0:
                    await self.button_callback(pin)
                    await asyncio.sleep_ms(self.debounce_ms)
            await asyncio.sleep_ms(self.polling_rate_ms)

    async def button_callback(self, pin):
        attr = self.hass.entities.get(self.thermostat_entity_id, {}).get('a', {})
        min_temp = float(attr.get('min_temp', 7))
        max_temp = float(attr.get('max_temp', 35))
        target_temp = float(attr.get('temperature', 7))
        current_temp = float(attr.get('current_temperature', 0))
        step = 0.5
        
        new_temp = target_temp
        if pin == self.b:
            new_temp = min_temp
        elif pin == self.a:
            new_temp = self.default_max_temp if self.default_max_temp is not None else max_temp
        elif pin == self.x:
            new_temp += step
        elif pin == self.y:
            new_temp -= step
        
        new_temp = min(max(round(new_temp * 2) / 2, min_temp), max_temp)
        if new_temp == target_temp:
            return
        
        await self.hass.action("climate", "set_temperature", {"temperature": new_temp}, self.thermostat_entity_id)
