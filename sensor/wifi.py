import network

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
        
        self.disconnect()
        self.connect()
        
    def disconnect(self):
        self.wlan.disconnect()
        self.wlan.active(False)
        
    def connect(self):
        self.wlan.active(True)
        self.wlan.connect(ssid, key)
        
        while not self.wlan.isconnected():
            time.sleep(5)
            print(wlan)
