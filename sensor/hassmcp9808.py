from mcp9808 import MCP9808
from machine import I2C
from datapoint import DataPoint
import asyncio

class HassMcp9808:
    def __init__(self, hass, scl, sda, temperature_config):
        self.i2c = I2C(0, scl=scl, sda=sda)
        self.mcp = MCP9808(i2c=self.i2c)
        self.hass = hass
        
        self.temperature_config = temperature_config
        
        # See https://ww1.microchip.com/downloads/en/DeviceDoc/25095A.pdf
        # Only report value changes outside of accuracy tolerance
        self.temperature = DataPoint(0.25)

    CREATION_PRIORITY = 1
    def create(provider):
        config = provider['config']['mcp9808']
        return HassMcp9808(provider['hass.Hass'], config['scl'], config['sda'], config['temperature'])
    
    async def start(self):
        while True:
            self.temperature.set_value(self.mcp.get_temp())
            
            if self.temperature.get_needs_update():
                await self.hass.send_update(self.temperature.get_value(), "°C", "temperature", **self.temperature_config)
                self.temperature.set_value_updated()
            
            await asyncio.sleep(1)
