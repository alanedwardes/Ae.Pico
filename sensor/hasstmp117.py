from tmp117 import TMP117
from machine import Pin, I2C
from datapoint import DataPoint
import asyncio

class HassTmp117:
    def __init__(self, hass, sda, scl, temperature_config):
        self.i2c = I2C(0, sda=Pin(sda), scl=Pin(scl))
        self.tmp = TMP117(self.i2c)
        self.hass = hass
        
        self.temperature_config = temperature_config
        
        # See https://www.ti.com/lit/ds/symlink/tmp117.pdf
        # Only report value changes outside of accuracy tolerance
        # Use 0.2 instead of 0.1 to avoid constant updates
        # E.g. when oscilating between 19.19 and 19.20
        self.temperature = DataPoint(0.2)

    CREATION_PRIORITY = 1
    def create(provider):
        config = provider['config']['tmp117']
        return HassTmp117(provider['hass.Hass'], config['sda'], config['scl'], config['temperature'])
    
    async def start(self):
        while True:
            self.temperature.set_value(self.tmp.temperature)
            
            if self.temperature.get_needs_update():
                await self.hass.send_update(self.temperature.get_value(), "°C", "temperature", **self.temperature_config)
                self.temperature.set_value_updated()
            
            await asyncio.sleep(1)