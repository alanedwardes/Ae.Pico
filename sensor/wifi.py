import network
import utime
import utime

class WiFi:
    
    def __init__(self, host, ssid, key):
        self.ssid = ssid
        self.key = key
        
        self.wlan = network.WLAN(network.STA_IF)
        self.wlan.config(pm = 0xa11140, hostname = host)
        
    def get_signal(self):
        return self.wlan.status('rssi')
        
    def ensure_connected(self):
        if self.wlan.isconnected():
            return
        
        self.disconnect()
        self.connect()
        
    def disconnect(self):
        self.wlan.deinit()
        
    def connect(self):
        self.wlan.active(True)
        self.wlan.connect(self.ssid, self.key)
        
        started_connect_time = utime.ticks_ms()
        while not self.wlan.isconnected():
            if utime.ticks_diff(utime.ticks_ms(), started_connect_time) > 20_000:
                raise Exception('Error connecting to WiFi')
            print("%04u-%02u-%02uT%02u:%02u:%02u" % utime.localtime()[0:6], self.wlan, self.wlan.status())
            utime.sleep(5)
        
        print("%04u-%02u-%02uT%02u:%02u:%02u" % utime.localtime()[0:6], "Connected", self.wlan, self.wlan.ifconfig())
