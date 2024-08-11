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
if config.motion_sensor.get('enabled', False):
    motion = machine.Pin(config.motion_sensor['pin'], machine.Pin.IN)

# Init BME280
if config.bme280_sensor.get('enabled', False):
    import bme280
    i2c_bme = machine.I2C(0, scl=config.bme280_sensor['scl_pin'], sda=config.bme280_sensor['sda_pin'])
    bme = bme280.BME280(i2c=i2c_bme)

# Init SCD4X
if config.scd4x_sensor.get('enabled', False):
    import scd4x
    i2c_scd4x = machine.I2C(0, scl=config.scd4x_sensor['scl_pin'], sda=config.scd4x_sensor['sda_pin'], freq=100000)
    scd = scd4x.SCD4X(i2c_scd4x)
    scd.start_periodic_measurement()

# Init Geiger
if config.geiger_sensor.get('enabled', False):
    from geiger import Geiger
    geiger_pin = machine.Pin(config.geiger_sensor['pin'], machine.Pin.IN)
    geiger = Geiger(config.geiger_sensor['tube_cpm_ratio'], geiger_pin, machine.Pin.IRQ_RISING, config.geiger_sensor['min_update_ms'], 0.01)
    
# Init WiFi
wifi = WiFi(config.wifi['host'], config.wifi['ssid'], config.wifi['key'])

# Init Home Assistant
hass = Hass(config.hass['url'], config.hass['token'])

def flash_led(flashes):
    duration = 0.2
    utime.sleep(duration)
    for flash in range(0, flashes):
        led.on()
        utime.sleep(duration)
        led.off()
        utime.sleep(duration)
   
def send_update(state, unit, device_class, friendly_name, sensor):
    hass.send_update(state, unit, device_class, friendly_name, sensor)
    gc.collect()
    flash_led(1)

motion_state = DataPoint()
def update_motion_sensor():
    if not config.motion_sensor.get('enabled', False):
        return
    
    motion_state.set_value(motion.value() == 1)

    if motion_state.get_needs_update():
        send_update("on" if motion_state.get_value() else "off", None, "motion", config.motion_sensor['friendly_name'], "binary_sensor." + config.motion_sensor['name'])
        motion_state.set_value_updated()

temperature = DataPoint(0.1)
humidity = DataPoint(0.5)

pressure = DataPoint(0.25)
def update_bme280_sensor():
    if not config.bme280_sensor.get('enabled', False):
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
    if not config.scd4x_sensor.get('enabled', False):
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

def update_geiger_sensor():
    if not config.geiger_sensor.get('enabled', False):
        return
    
    geiger.update()

    if geiger.datapoint.get_needs_update():
        send_update(geiger.datapoint.get_value(), "μSv/h", None, config.geiger_sensor['geiger_friendly_name'], "sensor." + config.geiger_sensor['geiger_name'])
        geiger.datapoint.set_value_updated()

wifi_sensor = DataPoint(5)
def update_wifi_sensor():
    wifi_sensor.set_value(wifi.get_signal())
    
    if wifi_sensor.get_needs_update():
        send_update(wifi_sensor.get_value(), "dBm", "signal_strength", config.wifi['rssi_friendly_name'], "sensor." + config.wifi['rssi_name'])
        wifi_sensor.set_value_updated()
    
server = ManagementServer()
def main_loop():
    wifi.update()

    if wifi.is_connected():
        update_motion_sensor()
        update_bme280_sensor()
        update_scd4x_sensor()
        update_geiger_sensor()
        update_wifi_sensor()
        server.update()

wd = machine.WDT(timeout=8388)
while True:
    wd.feed()
    try:
        main_loop()
    except Exception as e:
        print("%04u-%02u-%02uT%02u:%02u:%02u" % utime.localtime()[0:6],  e)
    
    machine.idle()
