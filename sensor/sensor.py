from machine import Pin
import network
import time
import ujson
import urequests
import gc
import config

led = Pin("LED", Pin.OUT)
motion = Pin(config.motion_sensor['pin'], Pin.IN)

wlan = network.WLAN(network.STA_IF)
wlan.active(True)
wlan.config(pm = 0xa11140, hostname = config.wifi['host'])

def connect_to_wifi():
    if not wlan.isconnected():
        print("Connecting to Wi-Fi...")
        wlan.connect(config.wifi['ssid'], config.wifi['key'])
        while not wlan.isconnected():
            led.on()
            time.sleep(0.01)
            led.off()
    print("Connected to Wi-Fi")
    
def send_update(motion_detected):
    print("Sending update: " + str(motion_detected))    
    
    data = {
        "state": "on" if motion_detected else "off",
        "attributes": {
            "device_class": "occupancy",
            "friendly_name": config.motion_sensor['friendly_name']
        }
    }

    headers = {
        "Authorization": "Bearer " + config.hass['token'],
        "Content-Type": "application/json"
    }

    response = urequests.post(config.hass['url'] + "/api/states/binary_sensor." + config.motion_sensor['name'], json=data, headers=headers)
    if response.status_code != 200:
        raise Exception("Status " + response.status_code + ": " + response.text)
    
    print("Updated state")

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
        send_update(current_motion_state)

    previous_motion_state = current_motion_state

def main_loop():  
    if not wlan.isconnected():
        print("Wi-Fi connection dropped. Reconnecting...")
        connect_to_wifi()
    
    update_motion_sensor()

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
