import gc
import management
import machine
import network
import clock
import picographics
import utime
import config
import remotetime
from wifi import WiFi

display = picographics.PicoGraphics(display=picographics.DISPLAY_PICO_DISPLAY_2, pen_type=picographics.PEN_P4, rotate=config.clock['rotate'])
display.set_backlight(1)

wifi = WiFi(config.wifi['host'], config.wifi['ssid'], config.wifi['key'])
time = remotetime.RemoteTime(config.clock['endpoint'], config.clock['update_time_ms'])

server = management.ManagementServer()

clock = clock.Clock(display)

def main_loop():
    clock.update()
    wifi.update()
    
    if wifi.is_connected():
        time.update()
        server.update()

wd = machine.WDT(timeout=8388)
while True:
    wd.feed()
    try:
        main_loop()
    except Exception as e:
        print("%04u-%02u-%02uT%02u:%02u:%02u" % utime.localtime()[0:6],  e)
    
    machine.idle()
