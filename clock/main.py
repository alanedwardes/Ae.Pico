import gc
import management
import machine
import network
import clock
import picographics
import utime
import config
from wifi import WiFi
from hass import Hass

display = picographics.PicoGraphics(display=picographics.DISPLAY_PICO_DISPLAY_2, pen_type=picographics.PEN_P4, rotate=config.clock['rotate'])
display.set_backlight(1)

wifi = WiFi(config.wifi['host'], config.wifi['ssid'], config.wifi['key'])
hass = Hass(config.hass['url'], config.hass['token'])

server = management.ManagementServer()

clock = clock.Clock(display)

last_updated_time = None
def update_time():
    global last_updated_time
    
    if last_updated_time is None or utime.ticks_diff(utime.ticks_ms(), last_updated_time) > config.clock['update_time_ms']:
        try:
            hass.set_time()
            last_updated_time = utime.ticks_ms()
            print('Time updated')
        except Exception as e:
            print('Error refreshing the time', e)
        finally:
            gc.collect()

def main_loop():
    clock.update()
    wifi.update()
    
    if wifi.is_connected():
        update_time()
        server.update()

wd = machine.WDT(timeout=8388)
while True:
    wd.feed()
    try:
        main_loop()
    except Exception as e:
        print("%04u-%02u-%02uT%02u:%02u:%02u" % utime.localtime()[0:6],  e)
    
    machine.idle()
