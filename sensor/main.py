import machine
import utime
import gc
import config
from datapoint import DataPoint
from hass import Hass
from wifi import WiFi
from management import ManagementServer

# Init LED
led = machine.Pin("LED", machine.Pin.OUT)

# Init motion sensor
if hasattr(config, 'motion_sensor'):
    motion = machine.Pin(config.motion_sensor['pin'], machine.Pin.IN)

# Init BME280
if hasattr(config, 'bme280_sensor'):
    import bme280
    i2c_bme = machine.I2C(0, scl=config.bme280_sensor['scl_pin'], sda=config.bme280_sensor['sda_pin'])
    bme = bme280.BME280(i2c=i2c_bme)

# Init MCP9808
if hasattr(config, 'mcp9808_sensor'):
    import mcp9808
    i2c_mcp = machine.I2C(0, scl=config.mcp9808_sensor['scl_pin'], sda=config.mcp9808_sensor['sda_pin'])
    mcp = mcp9808.MCP9808(i2c=i2c_mcp)

# Init SCD4X
if hasattr(config, 'scd4x_sensor'):
    import scd4x
    i2c_scd4x = machine.I2C(0, scl=config.scd4x_sensor['scl_pin'], sda=config.scd4x_sensor['sda_pin'], freq=100000)
    scd = scd4x.SCD4X(i2c_scd4x)
    scd.start_periodic_measurement()

# Init Geiger
if hasattr(config, 'geiger_sensor'):
    from geiger import Geiger
    geiger_pin = machine.Pin(config.geiger_sensor['pin'], machine.Pin.IN)
    geiger = Geiger(config.geiger_sensor['tube_cpm_ratio'], geiger_pin, machine.Pin.IRQ_RISING, config.geiger_sensor['min_update_ms'], 0.01)
    
# Init WiFi
wifi = WiFi(config.wifi['host'], config.wifi['ssid'], config.wifi['key'])

# Init Home Assistant
hass = Hass(config.hass['url'], config.hass['token'])
   
def send_update(state, unit, device_class, friendly_name, sensor):
    hass.send_update(state, unit, device_class, friendly_name, sensor)
    gc.collect()

motion_state = DataPoint()
def update_motion_sensor():
    if not hasattr(config, 'motion_sensor'):
        return
    
    motion_state.set_value(motion.value() == 1)

    if motion_state.get_needs_update():
        send_update("on" if motion_state.get_value() else "off", None, "motion", config.motion_sensor['friendly_name'], "binary_sensor." + config.motion_sensor['name'])
        motion_state.set_value_updated()

temperature = DataPoint(0.25)
humidity = DataPoint(0.5)

pressure = DataPoint(0.25)
def update_bme280_sensor():
    if not hasattr(config, 'bme280_sensor'):
        return
    
    current_temp, current_pressure, current_humidity = bme.float_values()
    
    temperature.set_value(current_temp)
    pressure.set_value(current_pressure)
    humidity.set_value(current_humidity)

    if temperature.get_needs_update():
        send_update(temperature.get_value(), "°C", "temperature", config.bme280_sensor['temp_friendly_name'], "sensor." + config.bme280_sensor['temp_name'])
        temperature.set_value_updated()
    
    if pressure.get_needs_update():
        send_update(pressure.get_value(), "hPa", "atmospheric_pressure", config.bme280_sensor['pressure_friendly_name'], "sensor." + config.bme280_sensor['pressure_name'])
        pressure.set_value_updated()
        
    if humidity.get_needs_update():
        send_update(humidity.get_value(), "%", "humidity", config.bme280_sensor['humidity_friendly_name'], "sensor." + config.bme280_sensor['humidity_name'])
        humidity.set_value_updated()

co2 = DataPoint(20)
def update_scd4x_sensor():
    if not hasattr(config, 'scd4x_sensor'):
        return
    
    temperature.set_value(scd.temperature)
    humidity.set_value(scd.relative_humidity)
    co2.set_value(scd.co2)
    
    if temperature.get_needs_update():
        send_update(temperature.get_value(), "°C", "temperature", config.scd4x_sensor['temp_friendly_name'], "sensor." + config.scd4x_sensor['temp_name'])
        temperature.set_value_updated()
    
    if co2.get_needs_update():
        send_update(co2.get_value(), "ppm", "carbon_dioxide", config.scd4x_sensor['co2_friendly_name'], "sensor." + config.scd4x_sensor['co2_name'])
        co2.set_value_updated()
        
    if humidity.get_needs_update():
        send_update(humidity.get_value(), "%", "humidity", config.scd4x_sensor['humidity_friendly_name'], "sensor." + config.scd4x_sensor['humidity_name'])
        humidity.set_value_updated()

def update_mcp9808_sensor():
    if not hasattr(config, 'mcp9808_sensor'):
        return
    
    temperature.set_value(mcp.get_temp())

    if temperature.get_needs_update():
        send_update(temperature.get_value(), "°C", "temperature", config.mcp9808_sensor['temp_friendly_name'], "sensor." + config.mcp9808_sensor['temp_name'])
        temperature.set_value_updated()

def update_geiger_sensor():
    if not hasattr(config, 'geiger_sensor'):
        return
    
    geiger.update()

    if geiger.datapoint.get_needs_update():
        send_update(geiger.datapoint.get_value(), "μSv/h", None, config.geiger_sensor['geiger_friendly_name'], "sensor." + config.geiger_sensor['geiger_name'])
        geiger.datapoint.set_value_updated()

server = ManagementServer()
def main_loop():
    wifi.update()

    if wifi.is_connected():
        led.on()
        update_motion_sensor()
        update_bme280_sensor()
        update_scd4x_sensor()
        update_mcp9808_sensor()
        update_geiger_sensor()
        server.update()
    else:
        led.toggle()

wd = machine.WDT(timeout=8388)
while True:
    wd.feed()
    try:
        main_loop()
    except Exception as e:
        print("%04u-%02u-%02uT%02u:%02u:%02u" % utime.localtime()[0:6], e)
    
    utime.sleep(0.1)
