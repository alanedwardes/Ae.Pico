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
            await self.__update()
            await asyncio.sleep(1)

    async def __update(self):        
        while True:
            if self.wlan.isconnected():
                return
            
            await asyncio.sleep(30)                
            if not self.wlan.isconnected():
                self.wlan.disconnect()
                self.wlan.connect(self.ssid, self.key)

    async def stop(self):
        pass
