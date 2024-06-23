# This is a CPython example, e.g. for a non-embedded, full-size Raspberry Pi
# It does not include a watchdog / WiFi management, only interactions with 
# Home Assistant (using the same logic as the MicroPython code)
#
# It requires the following pip modules:
# - requests
# - pimoroni-bme280

import utime
import config
from smbus2 import SMBus
from bme280 import BME280
from hass import Hass
from datapoint import DataPoint

bus = SMBus(1)
bme280 = BME280(i2c_dev=bus, i2c_addr=0x76)

hass = Hass(config.hass['url'], config.hass['token'])

temperature = DataPoint(0.1)
humidity = DataPoint(0.5)

pressure = DataPoint(0.25)
def update_bme280_sensor():
    if not config.bme280_sensor['enabled']:
        return
    current_temp = bme280.get_temperature()
    current_humidity = bme280.get_humidity()
    current_pressure = bme280.get_pressure()

    temperature.set_value(current_temp)
    pressure.set_value(current_pressure)
    humidity.set_value(current_humidity)

    if temperature.get_needs_update():
        hass.send_update(temperature.get_value(), "°C", "temperature", config.bme280_sensor['temp_friendly_name'], "sensor." + config.bme280_sensor['temp_name'])
        temperature.set_value_updated()

    if pressure.get_needs_update():
        hass.send_update(pressure.get_value(), "hPa", "atmospheric_pressure", config.bme280_sensor['pressure_friendly_name'], "sensor." + config.bme280_sensor['pressure_name'])
        pressure.set_value_updated()

    if humidity.get_needs_update():
        hass.send_update(humidity.get_value(), "%", "humidity", config.bme280_sensor['humidity_friendly_name'], "sensor." + config.bme280_sensor['humidity_name'])
        humidity.set_value_updated()

cpu_temperature = DataPoint(2)

def update_cpu_sensor():
    if not config.cpu_sensor['enabled']:
        return

    with open('/sys/class/thermal/thermal_zone0/temp') as f:
        current_cpu_temp = float(f.read()) / 1000

    cpu_temperature.set_value(current_cpu_temp)

    if cpu_temperature.get_needs_update():
        hass.send_update(cpu_temperature.get_value(), "°C", "temperature", config.cpu_sensor['temp_friendly_name'], "sensor." + config.cpu_sensor['temp_name'])
        cpu_temperature.set_value_updated()

def main_loop():
    update_bme280_sensor()
    update_cpu_sensor()

while True:
    try:
        main_loop()
    except Exception as e:
        print("%04u-%02u-%02uT%02u:%02u:%02u" % utime.localtime()[0:6],  e)
    utime.sleep(0.1)
