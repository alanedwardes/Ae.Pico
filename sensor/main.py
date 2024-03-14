import machine
import network
import time
import ujson
import urequests
import gc
import bme280
import scd4x
import config
import _thread
import datapoint

# Init LED
led = machine.Pin("LED", machine.Pin.OUT)

# Init motion sensor
motion = machine.Pin(config.motion_sensor['pin'], machine.Pin.IN) if config.motion_sensor['enabled'] else None

# Init BME280
i2c = machine.I2C(0, scl=config.bme280_sensor['scl_pin'], sda=config.bme280_sensor['sda_pin']) if config.bme280_sensor['enabled'] else None
bme = bme280.BME280(i2c=i2c) if config.bme280_sensor['enabled'] else None

# Init SCD4X
if config.scd4x_sensor['enabled']:
    i2c_scd4x = machine.I2C(0, scl=config.scd4x_sensor['scl_pin'], sda=config.scd4x_sensor['sda_pin'], freq=100000)
    scd = scd4x.SCD4X(i2c_scd4x)
    scd.start_periodic_measurement()

# Init WLAN
wlan = network.WLAN(network.STA_IF)
wlan.active(True)
wlan.config(pm = 0xa11140, hostname = config.wifi['host'])

def flash_led(flashes):
    duration = 0.2
    time.sleep(duration)
    for flash in range(0, flashes):
        led.on()
        time.sleep(duration)
        led.off()
        time.sleep(duration)

def connect_to_wifi():
    if not wlan.isconnected():
        flash_led(3)
        print("Connecting to Wi-Fi...")
        wlan.disconnect()
        wlan.connect(config.wifi['ssid'], config.wifi['key'])
        print("Connect returned")
        while wlan.isconnected() == False:
            time.sleep(1)
    print("Connected to Wi-Fi")
    flash_led(3)
    
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

    response = urequests.post(config.hass['url'] + "/api/states/" + sensor, data=ujson.dumps(data).encode('utf-8'), headers=headers)
    if not response.status_code in [200, 201]:
        raise Exception("Status " + str(response.status_code) + ": " + response.text)
    
    print("Updated state")
    flash_led(1)
    gc.collect()

motion_state = datapoint.DataPoint()
def update_motion_sensor():
    motion_state.set_value(motion.value() == 1)

    if motion_state.get_needs_update():
        send_update("on" if motion_state.get_value() else "off", None, "motion", config.motion_sensor['friendly_name'], "binary_sensor." + config.motion_sensor['name'])
        motion_state.set_value_updated()

temperature = datapoint.DataPoint(0.1)
humidity = datapoint.DataPoint(0.5)

pressure = datapoint.DataPoint(0.25)
def update_bme280_sensor():
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

last_tick_ms = time.ticks_ms()
def watchdog_thread():
    global last_tick_ms
    
    while True:
        time_since_last_tick_ms = time.ticks_diff(time.ticks_ms(), last_tick_ms)
        if time_since_last_tick_ms > 30_000:
            print('Watchdog detected hang. Attempting reset (debugger will disconnect)')
            machine.reset()
        time.sleep(1)

def main_loop():  
    if not wlan.isconnected():
        print("Wi-Fi connection dropped. Reconnecting...")
        connect_to_wifi()
    
    if config.motion_sensor['enabled']:
        update_motion_sensor()
        
    if config.bme280_sensor['enabled']:
        update_bme280_sensor()
        
    if config.scd4x_sensor['enabled']:
        update_scd4x_sensor()

flash_led(1)
time.sleep(2)

_thread.start_new_thread(watchdog_thread, ())

while True:
    last_tick_ms = time.ticks_ms()
    try:
        main_loop()
        time.sleep(0.1)
    except Exception as e:
        print("Something went wrong", e)
        flash_led(5)
        time.sleep(2)

print('exit')

