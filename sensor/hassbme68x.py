import asyncio
import machine
import datapoint
import bme680

class HassBme68x:
    def __init__(self, hass, sda, scl, address, temperature_config, pressure_config, humidity_config, resistance_config):
        self.i2c = machine.I2C(0, sda=sda, scl=scl)
        self.bme = bme680.BME680_I2C(self.i2c, address=address)
        self.hass = hass
        
        self.temperature_config = temperature_config
        self.pressure_config = pressure_config
        self.humidity_config = humidity_config
        self.resistance_config = resistance_config
        
        # See https://www.bosch-sensortec.com/media/boschsensortec/downloads/datasheets/bst-bme680-ds001.pdf
        # Only report value changes outside of accuracy tolerance
        self.temperature = datapoint.DataPoint(0.5)
        self.pressure = datapoint.DataPoint(1)
        self.humidity = datapoint.DataPoint(3)
        self.resistance = datapoint.DataPoint(10)

    CREATION_PRIORITY = 1
    def create(provider):
        config = provider['config']['bme68x']
        return HassBme68x(provider['hass.Hass'], config['sda'], config['scl'], config['address'], config['temperature'], config['pressure'], config['humidity'], config['resistance'])
    
    async def start(self):
        while True:            
            current_temp = await self.bme.temperature()
            current_pressure = await self.bme.pressure()
            current_humidity = await self.bme.humidity()
            current_resistance = await self.bme.gas()
            
            self.temperature.set_value(current_temp)
            self.pressure.set_value(current_pressure)
            self.humidity.set_value(current_humidity)
            self.resistance.set_value(current_resistance / 1000)
            
            if self.temperature.get_needs_update():
                await self.hass.send_update(self.temperature.get_value(), "°C", "temperature", **self.temperature_config)
                self.temperature.set_value_updated()
            
            if self.pressure.get_needs_update():
                await self.hass.send_update(self.pressure.get_value(), "hPa", "atmospheric_pressure", **self.pressure_config)
                self.pressure.set_value_updated()
                
            if self.humidity.get_needs_update():
                await self.hass.send_update(self.humidity.get_value(), "%", "humidity", **self.humidity_config)
                self.humidity.set_value_updated()
                
            if self.resistance.get_needs_update():
                await self.hass.send_update(self.resistance.get_value(), "kΩ", "resistance", **self.resistance_config)
                self.resistance.set_value_updated()
            
            await asyncio.sleep(1)
