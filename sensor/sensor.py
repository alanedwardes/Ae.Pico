from machine import Pin
import network
import time
import ujson
import urequests
import gc
import bme280
import config

# Init LED
led = Pin("LED", Pin.OUT)

# Init motion sensor
motion = Pin(config.motion_sensor['pin'], Pin.IN) if config.motion_sensor['enabled'] else None

# Init BME280
i2c = machine.I2C(0, scl=config.bme280_sensor['scl_pin'], sda=config.bme280_sensor['sda_pin']) if config.bme280_sensor['enabled'] else None
bme = bme280.BME280(i2c=i2c) if config.bme280_sensor['enabled'] else None

# Init WLAN
wlan = network.WLAN(network.STA_IF)
wlan.active(True)
wlan.config(pm = 0xa11140, hostname = config.wifi['host'])

def connect_to_wifi():
    if not wlan.isconnected():
        print("Connecting to Wi-Fi...")
        wlan.connect(config.wifi['ssid'], config.wifi['key'])
        print("Connect returned")
        while not wlan.isconnected():
            led.on()
            time.sleep(0.01)
            led.off()
    print("Connected to Wi-Fi")
    
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
    gc.collect()

last_motion_ms = 0
previous_motion_state = False
def update_motion_sensor():
    global last_motion_ms, previous_motion_state
    
    sensor_value = motion.value() == 1
    
    if sensor_value:
        last_motion_ms = time.ticks_ms()
        
    time_since_last_motion_ms = time.ticks_diff(time.ticks_ms(), last_motion_ms)
    
    current_motion_state = sensor_value or time_since_last_motion_ms < config.motion_sensor['timeout_ms']
    
    if current_motion_state != previous_motion_state:
        send_update("on" if current_motion_state else "off", None, "occupancy", config.motion_sensor['friendly_name'], "binary_sensor." + config.motion_sensor['name'])

    previous_motion_state = current_motion_state

last_temp = 0
last_pressure = 0
last_humidity = 0
def update_bme280_sensor():
    global last_temp, last_pressure, last_humidity
    
    current_temp, current_pressure, current_humidity = bme.float_values()
    
    temp_diff = abs(last_temp - current_temp)
    pressure_diff = abs(last_pressure - current_pressure)
    humidity_diff = abs(last_humidity - current_humidity)
    
    if temp_diff > 0.1:
        send_update(current_temp, "°C", "temperature", config.bme280_sensor['temp_friendly_name'], "sensor." + config.bme280_sensor['temp_name'])
    
    if pressure_diff > 0.25:
        send_update(current_pressure, "hPa", "atmospheric_pressure", config.bme280_sensor['pressure_friendly_name'], "sensor." + config.bme280_sensor['pressure_name'])
        
    if humidity_diff > 1:
        send_update(current_humidity, "%", "humidity", config.bme280_sensor['humidity_friendly_name'], "sensor." + config.bme280_sensor['humidity_name'])
    
    last_temp = current_temp
    last_pressure = current_pressure
    last_humidity = current_humidity

def main_loop():  
    if not wlan.isconnected():
        print("Wi-Fi connection dropped. Reconnecting...")
        connect_to_wifi()
    
    if config.motion_sensor['enabled']:
        update_motion_sensor()
        
    if config.bme280_sensor['enabled']:
        update_bme280_sensor()

while True:
    led.off()
    try:
        main_loop()
        time.sleep(0.1)
    except Exception as e:
        print("Something went wrong", e)
        led.on()
        time.sleep(2)

print('exit')

