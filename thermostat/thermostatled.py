import asyncio
from pimoroni import RGBLED

class ThermostatLed:
    def __init__(self, hass, nic, thermostat_entity_id, led, intensity):
        self.hass = hass
        self.nic = nic
        self.thermostat_entity_id = thermostat_entity_id
        self.led = RGBLED(*led)
        self.intensity = intensity
        self.is_heating = False
    
    CREATION_PRIORITY = 1
    def create(provider):
        config = provider['config']['thermostat']
        return ThermostatLed(provider['hassws.HassWs'], provider['nic'], config['entity_id'], config['leds'], config.get('led_intensity', 1))
    
    async def start(self):
        await self.hass.subscribe([self.thermostat_entity_id], self.thermostat_updated)
        while True:
            self.evaluate_led_color()
            await asyncio.sleep(1)
    
    def evaluate_led_color(self):
        if not self.hass.is_active() or not self.nic.isconnected():
            self.led.set_rgb(int(255 * self.intensity), 0, 0)
        elif self.is_heating:
            self.led.set_rgb(int(255 * self.intensity), int(69 * self.intensity), 0)
        else:
            self.led.set_rgb(0, 0, 0)

    def thermostat_updated(self, entity_id, entity):
        self.is_heating = entity.get('a', {}).get('hvac_action', 'idle') is "heating"
        self.evaluate_led_color()
