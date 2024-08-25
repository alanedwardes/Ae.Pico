STA_IF = 1

class WLAN:
    def __init__(self, type):
        pass
    
    def config(self, key):
        if key == 'ssid':
            return 'wibble'
        elif key == 'mac':
            return b'\xd8:\xdd\x97\xd3R'
        else:
            raise Exception('Not implemented')

    def status(self, key):
        if key == 'rssi':
            return -40
        else:
            raise Exception('Not implemented')

    def ifconfig(self):
        return ('192.168.168.1',)
