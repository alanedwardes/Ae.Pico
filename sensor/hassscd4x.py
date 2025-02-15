from scd4x import SCD4X
from machine import I2C
import asyncio
import machine
import datapoint

class HassScd4x:
    def __init__(self, hass, scl, sda, temperature_config, co2_config, humidity_config):
        self.i2c = I2C(0, scl=scl, sda=sda)
        self.scd = SCD4X(self.i2c)
        self.scd.start_periodic_measurement()
        self.hass = hass
        
        self.temperature_config = temperature_config
        self.co2_config = co2_config
        self.humidity_config = humidity_config
        
        # See https://sensirion.com/media/documents/48C4B7FB/66E05452/CD_DS_SCD4x_Datasheet_D1.pdf
        # Only report value changes outside of accuracy tolerance
        self.temperature = datapoint.DataPoint(0.8)
        self.co2 = datapoint.DataPoint(50)
        self.humidity = datapoint.DataPoint(6)

    CREATION_PRIORITY = 1
    def create(provider):
        config = provider['config']['scd4x']
        return HassScd4x(provider['hass.Hass'], config['scl'], config['sda'], config['temperature'], config['co2'], config['humidity'])
    
    async def start(self):
        while True:
            self.temperature.set_value(self.scd.temperature)
            self.co2.set_value(self.scd.co2)
            self.humidity.set_value(self.scd.relative_humidity)
            
            if self.temperature.get_needs_update():
                await self.hass.send_update(self.temperature.get_value(), "°C", "temperature", **self.temperature_config)
                self.temperature.set_value_updated()
            
            if self.co2.get_needs_update():
                await self.hass.send_update(self.co2.get_value(), "ppm", "carbon_dioxide", **self.co2_config)
                self.co2.set_value_updated()
                
            if self.humidity.get_needs_update():
                await self.hass.send_update(self.humidity.get_value(), "%", "humidity", **self.humidity_config)
                self.humidity.set_value_updated()
            
            await asyncio.sleep(1)
