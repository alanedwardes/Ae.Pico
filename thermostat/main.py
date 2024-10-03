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
display.set_backlight(1)

wifi = WiFi(config.wifi['host'], config.wifi['ssid'], config.wifi['key'])
hass = HassWs(config.hass['ws'], config.hass['token'])
time = remotetime.RemoteTime(config.clock['endpoint'], config.clock['update_time_ms'])

server = management.ManagementServer()

thermostat = thermostat.Thermostat(display)

def entities_updated(entities):
    entity = entities[config.thermostat['entity_id']]['a']
    thermostat.entity = {
        'min_temp': float(entity.get('min_temp')),
        'max_temp': float(entity.get('max_temp')),
        'current_temperature': float(entity.get('current_temperature')),
        'temperature': float(entity.get('temperature')),
        'target_temp_step': float(entity.get('target_temp_step')),
        'hvac_action': entity.get('hvac_action')
   }

hass.entities_updated = entities_updated
hass.subscribe(config.thermostat['entity_id'])

def update_led():
    hvac_action = thermostat.entity['hvac_action']
    if hvac_action == "idle":
        led.set_rgb(0, 0, 0)
    elif hvac_action == "heating":
        led.set_rgb(255, 69, 0)

def main_loop():
    thermostat.update()
    wifi.update()
    
    if wifi.is_connected():
        if len(input_events):
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
            
        
        server.update()
        hass.update()
        update_led()
        time.update()

#wd = machine.WDT(timeout=8388)
while True:
    #wd.feed()
    try:
        main_loop()
    except Exception as e:
        print("%04u-%02u-%02uT%02u:%02u:%02u" % utime.localtime()[0:6],  e)
    
    machine.idle()