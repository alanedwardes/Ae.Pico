import asyncio
import binascii
import textbox

class StartupDisplay:
    def __init__(self, display, nic):
        self.display = display
        self.nic = nic
        self.display_width, self.display_height = self.display.get_bounds()
        self.pending_activation = True
    
    CREATION_PRIORITY = 1
    def create(provider):
        return StartupDisplay(provider['display'], provider['nic'])
    
    async def start(self):
        await asyncio.Event().wait()
        
    def should_activate(self):
        return self.pending_activation

    async def activate(self):
        self.pending_activation = False
        while True:
            self.update()
            await asyncio.sleep(0.1)

    def update(self):
        y_start = 70
        
        # Clear the display area
        self.display.rect(0, y_start, self.display_width, self.display_height - y_start, 0x0000, True)
        
        y = y_start + 10
        x = 10
        width = self.display_width - 20
        line_height = 30
        
        # IP Address
        try:
            ip = self.nic.ifconfig()[0]
        except Exception:
            ip = "?"
        
        textbox.draw_textbox(self.display, f"IP: {ip}", x, y, width, line_height, color=0xFFFF, font='small', align='left')
        y += line_height
        
        # Hostname
        try:
            hostname = self.nic.config('hostname')
        except Exception:
            hostname = "?"
            
        textbox.draw_textbox(self.display, f"Host: {hostname}", x, y, width, line_height, color=0xFFFF, font='small', align='left')
        y += line_height
        
        # SSID
        try:
            ssid = self.nic.config('ssid')
        except Exception:
            ssid = "?"
            
        textbox.draw_textbox(self.display, f"WiFi: {ssid}", x, y, width, line_height, color=0xFFFF, font='small', align='left')
        y += line_height

        # MAC Address
        try:
            mac_bytes = self.nic.config('mac')
            mac = binascii.hexlify(mac_bytes, ':').decode().upper()
        except Exception:
            mac = "?"
            
        textbox.draw_textbox(self.display, f"MAC: {mac}", x, y, width, line_height, color=0xFFFF, font='small', align='left')
        y += line_height
        
        # Signal Strength
        try:
            rssi = self.nic.status('rssi')
        except Exception:
            rssi = "?"
            
        textbox.draw_textbox(self.display, f"Signal: {rssi} dBm", x, y, width, line_height, color=0xFFFF, font='small', align='left')
