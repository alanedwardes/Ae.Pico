import gc
import management
import machine
import network
import thermostat
import picographics
from pimoroni import RGBLED
import utime
import config
import ujson
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

display = picographics.PicoGraphics(display=picographics.DISPLAY_PICO_DISPLAY_2, pen_type=picographics.PEN_P4, rotate=config.clock['rotate'])
display.set_backlight(1)

wifi = WiFi(config.wifi['host'], config.wifi['ssid'], config.wifi['key'])
hass = HassWs(config.hass['ws'], config.hass['token'])

server = management.ManagementServer()

thermostat = thermostat.Thermostat(display)

def entities_updated(entities):
    thermostat.entity = entities[config.thermostat['entity_id']]

hass.entities_updated = entities_updated
hass.subscribe(config.thermostat['entity_id'])

def update_led():
    hvac_action = thermostat.entity['a']['hvac_action']
    if hvac_action == "idle":
        led.set_rgb(0, 0, 0)
    elif hvac_action == "heating":
        led.set_rgb(255, 69, 0)

def main_loop():
    thermostat.update()
    wifi.update()
    
    if wifi.is_connected():
        if len(input_events):
            attr = thermostat.entity['a']
            min_temp = attr['min_temp']
            max_temp = attr['max_temp']
            target_temp = attr['temperature']
            step = attr['target_temp_step']
            current_temp = attr['current_temperature']
            
            event = input_events.pop()
            if event == "off":
                hass.action("climate", "set_temperature", {"temperature":min_temp}, config.thermostat['entity_id'])
            elif event == "on":
                hass.action("climate", "set_temperature", {"temperature":current_temp}, config.thermostat['entity_id'])
            elif event == "up":
                hass.action("climate", "set_temperature", {"temperature":min(max_temp, target_temp + step)}, config.thermostat['entity_id'])
            elif event == "down":
                hass.action("climate", "set_temperature", {"temperature":max(min_temp, target_temp - step)}, config.thermostat['entity_id'])
        
        server.update()
        hass.update()
        update_led()

#wd = machine.WDT(timeout=8388)
while True:
    #wd.feed()
    try:
        main_loop()
    except Exception as e:
        print("%04u-%02u-%02uT%02u:%02u:%02u" % utime.localtime()[0:6],  e)
    
    machine.idle()
