from os import uname
from datapoint import DataPoint
from asyncio import sleep

class HassCpu:
    class Linux:
        def __init__(self):
            self.datapoint = DataPoint(1)
        
        def update(self):
            with open('/sys/class/thermal/thermal_zone0/temp') as f:
                self.datapoint.set_value(float(f.read()) / 1000)

    class Rp2:
        def __init__(self):
            # See https://datasheets.raspberrypi.com/rp2040/rp2040-datasheet.pdf
            # Only report value changes outside of accuracy tolerance
            self.datapoint = DataPoint(1)
            from machine import ADC
            self.adc = ADC(4)
        
        def update(self):
            voltage = self.adc.read_u16() * (3.3 / 65535.0)
            temperature = 27 - (voltage - 0.706) / 0.001721
            return self.datapoint.set_value(temperature)

    def __init__(self, hass, temperature_config, implementation):
        self.hass = hass
        self.temperature_config = temperature_config        
        self.implementation = implementation

    CREATION_PRIORITY = 1
    def create(provider):
        implentation = None

        if uname().sysname == 'rp2':
            implentation = HassCpu.Rp2()
        elif uname().sysname == 'Linux':
            implentation = HassCpu.Linux()
        else:
            return None
        
        config = provider['config']['cpu']
        return HassCpu(provider['hass.Hass'], config['temperature'], implentation)
    
    async def start(self):
        while True:
            self.implementation.update()
            
            if self.implementation.datapoint.get_needs_update():
                await self.hass.send_update(self.implementation.datapoint.get_value(), "°C", "temperature", **self.temperature_config)
                self.implementation.datapoint.set_value_updated()
            
            await sleep(1)
