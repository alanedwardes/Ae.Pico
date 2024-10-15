import gc
import network
import asyncio
import management
import machine
from buttons import Buttons
import thermostat
import picographics
from pimoroni import RGBLED
import config
import remotetime
import runner
from wifi import WiFi
from hassws import HassWs

led = RGBLED(6, 7, 8)

display = picographics.PicoGraphics(display=picographics.DISPLAY_PICO_DISPLAY_2, pen_type=picographics.PEN_P4, rotate=config.thermostat['rotate'])

nic = network.WLAN(network.STA_IF)

wifi = WiFi(config.wifi['host'], config.wifi['ssid'], config.wifi['key'], nic)
hass = HassWs(config.hass['ws'], config.hass['token'], nic)

swa = machine.Pin(12, machine.Pin.IN, machine.Pin.PULL_UP)
swb = machine.Pin(13, machine.Pin.IN, machine.Pin.PULL_UP)
swx = machine.Pin(14, machine.Pin.IN, machine.Pin.PULL_UP)
swy = machine.Pin(15, machine.Pin.IN, machine.Pin.PULL_UP)

buttons = Buttons()

async def button_callback(pin):
    attr = hass.entities.get(config.thermostat['entity_id'], {}).get('a', {})
    min_temp = float(attr.get('min_temp', 7))
    max_temp = float(attr.get('max_temp', 35))
    target_temp = float(attr.get('temperature', 7))
    current_temp = float(attr.get('current_temperature', 0))
    step = 0.5
    
    new_temp = target_temp
    if pin == swb:
        new_temp = min_temp
    elif pin == swa:
        new_temp = current_temp
    elif pin == swx:
        new_temp += step
    elif pin == swy:
        new_temp -= step
    
    new_temp = min(max(round(new_temp * 2) / 2, min_temp), max_temp)
    if new_temp == target_temp:
        return
    
    await hass.action("climate", "set_temperature", {"temperature": new_temp}, config.thermostat['entity_id'])

buttons.bind(swa, button_callback)
buttons.bind(swb, button_callback)
buttons.bind(swx, button_callback)
buttons.bind(swy, button_callback)

time = remotetime.RemoteTime(config.clock['endpoint'], config.clock['update_time_ms'], nic)

server = management.ManagementServer()

thermostat = thermostat.Thermostat(display, config.thermostat.get('middle_row', []), config.thermostat.get('bottom_row', []))

display.set_backlight(1)
def occupancy_updated(entity_id, entity):
    display.set_backlight(1 if entity['s'] == 'on' else 0)
hass.subscribe(config.thermostat.get('occupancy_entity_id', None), occupancy_updated)

#not hass.is_active() or not wifi.is_connected()

def entity_updated(entity_id, entity):
    thermostat.entities[entity_id] = entity
    if entity_id == config.thermostat['entity_id']:
        hvac_action = entity.get('a', {}).get('hvac_action', 'idle')
        if hvac_action == "idle":
            led.set_rgb(0, 0, 0)
        elif hvac_action == "heating":
            led.set_rgb(255, 69, 0)

for subscription in config.thermostat.get('middle_row', []) + config.thermostat.get('bottom_row', []):
    hass.subscribe(subscription['entity_id'], entity_updated)

runner.start(buttons, thermostat, wifi, server, hass, time)
