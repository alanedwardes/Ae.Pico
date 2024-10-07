import management
import machine
import thermostat
import picographics
from pimoroni import RGBLED
import utime
import config
import remotetime
from wifi import WiFi
from hassws import HassWs

input_events = []

swa = machine.Pin(12, machine.Pin.IN, machine.Pin.PULL_UP)
swa.irq(lambda p: input_events.append('on'), trigger=machine.Pin.IRQ_FALLING)

swb = machine.Pin(13, machine.Pin.IN, machine.Pin.PULL_UP)
swb.irq(lambda p: input_events.append('off'), trigger=machine.Pin.IRQ_FALLING)

swx = machine.Pin(14, machine.Pin.IN, machine.Pin.PULL_UP)
swx.irq(lambda p: input_events.append('up'), trigger=machine.Pin.IRQ_FALLING)

swy = machine.Pin(15, machine.Pin.IN, machine.Pin.PULL_UP)
swy.irq(lambda p: input_events.append('down'), trigger=machine.Pin.IRQ_FALLING)

led = RGBLED(6, 7, 8)

display = picographics.PicoGraphics(display=picographics.DISPLAY_PICO_DISPLAY_2, pen_type=picographics.PEN_P4, rotate=config.thermostat['rotate'])

wifi = WiFi(config.wifi['host'], config.wifi['ssid'], config.wifi['key'])
hass = HassWs(config.hass['ws'], config.hass['token'])
time = remotetime.RemoteTime(config.clock['endpoint'], config.clock['update_time_ms'])

server = management.ManagementServer()

thermostat = thermostat.Thermostat(display)

occupancy_detected = False
last_activity_time = utime.ticks_ms()

def entities_updated(entities):    
    occupancy_state = entities.get(config.thermostat.get('occupancy_entity_id', None), {}).get('s', None)
    if occupancy_state is not None:
        global occupancy_detected
        occupancy_detected = occupancy_state == 'on'
    
    thermostat_entity = entities.get(config.thermostat['entity_id'], {})
    if thermostat_entity is not None:
        attrs = thermostat_entity['a']
        thermostat.entity = {
            'min_temp': float(attrs.get('min_temp')),
            'max_temp': float(attrs.get('max_temp')),
            'current_temperature': float(attrs.get('current_temperature')),
            'temperature': float(attrs.get('temperature')),
            'target_temp_step': float(attrs.get('target_temp_step')),
            'hvac_action': attrs.get('hvac_action')
        }
    
    current_temperature_entity = entities.get(config.thermostat['current_temperature_entity_id'], {})
    if current_temperature_entity is not None:
        thermostat.weather['current_temperature'] = float(current_temperature_entity['s'])

    maximum_temperature_entity = entities.get(config.thermostat['maximum_temperature_entity_id'], {})
    if maximum_temperature_entity is not None:
        thermostat.weather['maximum_temperature'] = float(maximum_temperature_entity['s'])

    current_precipitation_entity = entities.get(config.thermostat['current_precipitation_entity_id'], {})
    if current_precipitation_entity is not None:
        thermostat.weather['current_precipitation'] = float(current_precipitation_entity['s'])

def update_backlight():
    ms_since_last_activity = utime.ticks_diff(utime.ticks_ms(), last_activity_time)
    display.set_backlight(1 if occupancy_detected or ms_since_last_activity < 60_000 else 0)

hass.entities_updated = entities_updated
hass.subscribe(config.thermostat['entity_id'])
hass.subscribe(config.thermostat.get('occupancy_entity_id', None))
hass.subscribe(config.thermostat.get('current_temperature_entity_id', None))
hass.subscribe(config.thermostat.get('maximum_temperature_entity_id', None))
hass.subscribe(config.thermostat.get('current_precipitation_entity_id', None))

def update_led():
    hvac_action = thermostat.entity['hvac_action']
    if not hass.is_active() or not wifi.is_connected():
        led.set_rgb(255, 0, 0)
    elif hvac_action == "idle":
        led.set_rgb(0, 0, 0)
    elif hvac_action == "heating":
        led.set_rgb(255, 69, 0)

def update_input():
    if len(input_events) == 0 or not hass.is_active():
        return
    
    global last_activity_time
    last_activity_time = utime.ticks_ms()  
    attr = thermostat.entity
    min_temp = attr['min_temp']
    max_temp = attr['max_temp']
    target_temp = attr['temperature']
    step = 0.5
    current_temp = attr['current_temperature']
    
    event = input_events.pop()
    new_temp = target_temp
    if event == "off":
        new_temp = min_temp
    elif event == "on":
        new_temp = current_temp
    elif event == "up":
        new_temp += step
    elif event == "down":
        new_temp -= step
        
    hass.action("climate", "set_temperature", {"temperature":min(max(round(new_temp * 2) / 2, min_temp), max_temp)}, config.thermostat['entity_id'])

def main_loop():
    update_backlight()
    update_led()
    update_input()
    thermostat.update()
    wifi.update()
    
    if wifi.is_connected():
        server.update()
        hass.update()
        time.update()

#wd = machine.WDT(timeout=8388)
while True:
    #wd.feed()
    try:
        main_loop()
    except Exception as e:
        print("%04u-%02u-%02uT%02u:%02u:%02u" % utime.localtime()[0:6],  e)
    
    machine.idle()
