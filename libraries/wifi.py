import machine
import network
import asyncio

class WiFi:
    
    def __init__(self, host, ssid, key, nic):
        self.ssid = ssid
        self.key = key
        self.wlan = nic
        self.wlan.config(hostname = host)
        self.wlan.active(True)
              
    async def start(self):
        if not self.wlan.isconnected():
            self.wlan.connect(self.ssid, self.key)
        
        while True:
            for i in range(0, 5):
                if self.wlan.isconnected():
                    break
            
                await asyncio.sleep(30)                
                if not self.wlan.isconnected():
                    self.wlan.disconnect()
                    self.wlan.connect(self.ssid, self.key)
            
                machine.reset()
            await asyncio.sleep(1)
            
    async def stop(self):
        pass
