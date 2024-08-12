import management
import machine
import network
import utime

wlan = network.WLAN(network.STA_IF)
wlan.active(True)
wlan.config(hostname = "hostname")
wlan.connect("ssid", "password")

while not wlan.isconnected():
    print(wlan)
    utime.sleep(1)

server = management.ManagementServer()

while True:
    server.update()
    machine.idle()
