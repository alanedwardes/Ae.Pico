import machine
import time
import ujson
import urequests
import gc
import config
import watchdog
import datapoint
from wifi import WiFi

# Init LED
led = machine.Pin("LED", machine.Pin.OUT)

# Init motion sensor
if config.motion_sensor['enabled']:
    motion = machine.Pin(config.motion_sensor['pin'], machine.Pin.IN)

# Init BME280
if config.bme280_sensor['enabled']:
    import bme280
    i2c_bme = machine.I2C(0, scl=config.bme280_sensor['scl_pin'], sda=config.bme280_sensor['sda_pin'])
    bme = bme280.BME280(i2c=i2c_bme)

# Init SCD4X
if config.scd4x_sensor['enabled']:
    import scd4x
    i2c_scd4x = machine.I2C(0, scl=config.scd4x_sensor['scl_pin'], sda=config.scd4x_sensor['sda_pin'], freq=100000)
    scd = scd4x.SCD4X(i2c_scd4x)
    scd.start_periodic_measurement()
    
# Init WiFi
wifi = WiFi(config.wifi['host'], config.wifi['ssid'], config.wifi['key'])

def flash_led(flashes):
    duration = 0.2
    time.sleep(duration)
    for flash in range(0, flashes):
        led.on()
        time.sleep(duration)
        led.off()
        time.sleep(duration)
   
def send_update(state, unit, device_class, friendly_name, sensor):
    print("Sending update for " + sensor + "=" + str(state))    
    
    data = {
        "state": state,
        "attributes": {
            "device_class": device_class,
            "friendly_name": friendly_name
        }
    }
    
    if unit is not None:
        data['attributes']['unit_of_measurement'] = unit
        data['attributes']['state_class'] = "measurement"

    headers = {
        "Authorization": "Bearer " + config.hass['token'],
        "Content-Type": "application/json; charset=utf-8"
    }

    response = urequests.post(config.hass['url'] + "/api/states/" + sensor, data=ujson.dumps(data).encode('utf-8'), headers=headers, timeout=5)
    if not response.status_code in [200, 201]:
        raise Exception("Status " + str(response.status_code) + ": " + response.text)
    
    print("Updated state")
    flash_led(1)
    gc.collect()

motion_state = datapoint.DataPoint()
def update_motion_sensor():
    if not config.motion_sensor['enabled']:
        return
    
    motion_state.set_value(motion.value() == 1)

    if motion_state.get_needs_update():
        send_update("on" if motion_state.get_value() else "off", None, "motion", config.motion_sensor['friendly_name'], "binary_sensor." + config.motion_sensor['name'])
        motion_state.set_value_updated()

temperature = datapoint.DataPoint(0.1)
humidity = datapoint.DataPoint(0.5)

pressure = datapoint.DataPoint(0.25)
def update_bme280_sensor():
    if not config.bme280_sensor['enabled']:
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

co2 = datapoint.DataPoint(20)
def update_scd4x_sensor():
    if not config.scd4x_sensor['enabled']:
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

def main_loop():  
    wifi.ensure_connected()
    update_motion_sensor()
    update_bme280_sensor()
    update_scd4x_sensor()

wd = watchdog.Watchdog()
while True:
    wd.feed()
    try:
        main_loop()
    except Exception as e:
        print(e)
    time.sleep(0.1)
