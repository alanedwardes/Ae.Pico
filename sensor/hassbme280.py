import bme280
import asyncio
import machine
import datapoint

class HassBme280:
    def __init__(self, hass, i2c, temperature_config, pressure_config, humidity_config):
        self.i2c = machine.I2C(i2c['bus'], **i2c['options'])
        self.bme = bme280.BME280(i2c=self.i2c)
        self.hass = hass
        
        self.temperature_config = temperature_config
        self.pressure_config = pressure_config
        self.humidity_config = humidity_config
        
        # See https://www.bosch-sensortec.com/media/boschsensortec/downloads/datasheets/bst-bme280-ds002.pdf
        # Only report value changes outside of accuracy tolerance
        self.temperature = datapoint.DataPoint(0.5)
        self.pressure = datapoint.DataPoint(1)
        self.humidity = datapoint.DataPoint(3)

    CREATION_PRIORITY = 1
    def create(provider):
        config = provider['config']['bme280']
        return HassBme280(provider['hass.Hass'], config['i2c'], config['temperature'], config['pressure'], config['humidity'])
    
    async def start(self):
        while True:
            current_temp, current_pressure, current_humidity = self.bme.float_values()
            
            self.temperature.set_value(current_temp)
            self.pressure.set_value(current_pressure)
            self.humidity.set_value(current_humidity)
            
            if self.temperature.get_needs_update():
                await self.hass.send_update(self.temperature.get_value(), "°C", "temperature", **self.temperature_config)
                self.temperature.set_value_updated()
            
            if self.pressure.get_needs_update():
                await self.hass.send_update(self.pressure.get_value(), "hPa", "atmospheric_pressure", **self.pressure_config)
                self.pressure.set_value_updated()
                
            if self.humidity.get_needs_update():
                await self.hass.send_update(self.humidity.get_value(), "%", "humidity", **self.humidity_config)
                self.humidity.set_value_updated()
            
            await asyncio.sleep(1)
