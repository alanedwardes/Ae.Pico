import machine
import network
import time
import ujson
import urequests
import gc
import bme280
import config
import _thread

# Init LED
led = machine.Pin("LED", machine.Pin.OUT)

# Init motion sensor
motion = machine.Pin(config.motion_sensor['pin'], machine.Pin.IN) if config.motion_sensor['enabled'] else None

# Init BME280
i2c = machine.I2C(0, scl=config.bme280_sensor['scl_pin'], sda=config.bme280_sensor['sda_pin']) if config.bme280_sensor['enabled'] else None
bme = bme280.BME280(i2c=i2c) if config.bme280_sensor['enabled'] else None

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
        last_temp = current_temp
    
    if pressure_diff > 0.25:
        send_update(current_pressure, "hPa", "atmospheric_pressure", config.bme280_sensor['pressure_friendly_name'], "sensor." + config.bme280_sensor['pressure_name'])
        last_pressure = current_pressure
        
    if humidity_diff > 1:
        send_update(current_humidity, "%", "humidity", config.bme280_sensor['humidity_friendly_name'], "sensor." + config.bme280_sensor['humidity_name'])
        last_humidity = current_humidity

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


