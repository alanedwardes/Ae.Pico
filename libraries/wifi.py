import machine
import network
import utime
import asyncio

class WiFi:
    
    def __init__(self, host, ssid, key, nic):
        self.ssid = ssid
        self.key = key
        self.wlan = nic
        self.wlan.config(hostname = host)
        
    def get_signal(self):
        return self.wlan.status('rssi')
    
    def get_mac_address(self):
        mac = self.wlan.config('mac')
        return ':'.join([f"{b:02x}" for b in mac])
    
    def get_ip_address(self):
        return self.wlan.ifconfig()[0]
       
    def is_connected(self):
        return self.wlan.status() == network.STAT_GOT_IP
    
    def is_connecting(self):
        return not self.is_failed() and not self.is_connected()

    def is_failed(self):
        return self.wlan.status() == network.STAT_CONNECT_FAIL or \
               self.wlan.status() == network.STAT_NO_AP_FOUND or \
               self.wlan.status() == network.STAT_IDLE or \
               self.wlan.status() == network.STAT_WRONG_PASSWORD
              
    async def start(self):
        if not self.is_connected():
            self.connect()
        
        while True:
            await self.update()
            await asyncio.sleep(1)
            
    async def stop(self):
        pass
    
    async def update(self):        
        for i in range(0, 5):
            if self.is_connected():
                return
            
            self.__log(self.get_status())
        
            #if self.is_connecting():
            await asyncio.sleep(30)                
            if not self.is_connected():
                self.__log('SOFT TIMEOUT')
                self.disconnect()
                self.connect()
        
        self.__log('HARD TIMEOUT')
        machine.reset()
        
    def get_status(self):
        status_map = {
            network.STAT_CONNECTING: 'CONNECTING',
            network.STAT_CONNECT_FAIL: 'CONNECT_FAIL',
            network.STAT_GOT_IP: 'GOT_IP',
            network.STAT_IDLE: 'IDLE',
            network.STAT_NO_AP_FOUND: 'NO_AP_FOUND',
            network.STAT_WRONG_PASSWORD: 'WRONG_PASSWORD',
            # Non-standard, see https://www.raspberrypi.com/documentation/pico-sdk/networking.html
            2: 'LINK_NOIP'
        }
        
        return status_map.get(self.wlan.status(), str(self.wlan.status()))
        
    def disconnect(self):
        self.wlan.disconnect()

    def __log(self, message):
        print('WiFi', message)

    def connect(self):
        self.__log('CONNECT')
        self.wlan.active(True)
        self.wlan.connect(self.ssid, self.key)
