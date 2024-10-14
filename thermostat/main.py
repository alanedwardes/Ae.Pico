import gc
import asyncio
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
from sys import print_exception

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

thermostat = thermostat.Thermostat(display, config.thermostat.get('middle_row', []), config.thermostat.get('bottom_row', []))

occupancy_detected = False
last_activity_time = utime.ticks_ms()

def occupancy_updated(entity_id, entity):
    global occupancy_detected
    occupancy_detected = entity['s'] == 'on'

def update_backlight():
    ms_since_last_activity = utime.ticks_diff(utime.ticks_ms(), last_activity_time)
    display.set_backlight(1 if occupancy_detected or ms_since_last_activity < 60_000 else 0)

hass.subscribe(config.thermostat.get('occupancy_entity_id', None), occupancy_updated)

def entity_updated(entity_id, entity):
    thermostat.entities[entity_id] = entity

for subscription in config.thermostat.get('middle_row', []) + config.thermostat.get('bottom_row', []):
    hass.subscribe(subscription['entity_id'], entity_updated)

def update_led():
    hvac_action = hass.entities.get(config.thermostat['entity_id'], {}).get('a', {}).get('hvac_action', 'idle')
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
    attr = hass.entities.get(config.thermostat['entity_id'], {}).get('a', {})
    min_temp = float(attr.get('min_temp', 7))
    max_temp = float(attr.get('max_temp', 35))
    target_temp = float(attr.get('temperature', 7))
    step = 0.5
    current_temp = float(attr.get('current_temperature', 0))
    
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
    
    asyncio.create_task(hass.action("climate", "set_temperature", {"temperature":min(max(round(new_temp * 2) / 2, min_temp), max_temp)}, config.thermostat['entity_id'])())

class Main:
    async def start(self):
        while True:
            update_backlight()
            update_led()
            update_input()
            await asyncio.sleep_ms(100)
    async def stop(self):
        pass

def set_global_exception():
    def handle_exception(loop, context):
        import sys
        sys.print_exception(context["exception"])
        sys.exit()
    loop = asyncio.get_event_loop()
    loop.set_exception_handler(handle_exception)

async def start_component(component):
    while True:
        try:
            await component.start()
        except Exception as e:
            gc.collect()
            import sys
            sys.print_exception(e)
            await asyncio.sleep(1)
        finally:
            await component.stop()

main = Main()

async def run():
    set_global_exception()
    await asyncio.gather(start_component(thermostat), start_component(wifi), start_component(server), start_component(main), start_component(hass), start_component(time))

wifi.disconnect()
try:
    asyncio.run(run())
finally:
    asyncio.new_event_loop()
