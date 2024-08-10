import network
import utime

class WiFi:
    
    def __init__(self, host, ssid, key):
        self.ssid = ssid
        self.key = key
        self.started_connect_time = utime.ticks_ms()
        
        self.wlan = network.WLAN(network.STA_IF)
        self.wlan.config(pm = 0xa11140, hostname = host)
        
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
    
    def ensure_connected(self):      
        while not self.is_connected():
            self.update()
            utime.sleep(1)
    
    def update(self):
        # No action if connected
        if self.is_connected():
            return
        
        self.__log(self.get_status())
        
        # If connecting, monitor for timeout
        if self.is_connecting():
            if self.time_since_started_connecting() < 30_000:
                # Still connecting
                return
            else:
                self.__log('TIMEOUT')
        
        # If not connecting, connect
        self.disconnect()
        self.connect()
        
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
        self.wlan.deinit()
        
    def time_since_started_connecting(self):
        return utime.ticks_diff(utime.ticks_ms(), self.started_connect_time)

    def __log(self, message):
        print('WiFi', message)

    def connect(self):
        self.__log('CONNECT')
        self.wlan.active(True)
        self.wlan.connect(self.ssid, self.key)
        self.started_connect_time = utime.ticks_ms()
