import network
import utime

class WiFi:
    wlan = None
    ssid = None
    key = None
    
    def __init__(self, host, ssid, key):
        self.ssid = ssid
        self.key = key
        
        self.wlan = network.WLAN(network.STA_IF)
        self.wlan.config(pm = 0xa11140, hostname = host)
        
    def ensure_connected(self):
        if self.wlan.isconnected():
            return
        
        self.connect()
        
    def disconnect(self):
        self.wlan.disconnect()
        self.wlan.active(False)
        
    def connect(self):
        self.wlan.active(True)
        self.wlan.connect(self.ssid, self.key)
        
        while not self.wlan.isconnected():
            utime.sleep(5)
            print(self.wlan)
