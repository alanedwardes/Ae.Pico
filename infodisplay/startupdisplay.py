import asyncio
import binascii
import textbox

class StartupDisplay:
    def __init__(self, display, nic, start_y):
        self.display = display
        self.nic = nic
        self.start_y = start_y
        self.display_width, self.display_height = self.display.get_bounds()
        self.pending_activation = True

        self.x = 10
        self.width = self.display_width - 20
        self.line_height = 30
        self.ip_y = start_y + 10
        self.host_y = self.ip_y + self.line_height
        self.ssid_y = self.host_y + self.line_height
        self.mac_y = self.ssid_y + self.line_height
        self.signal_y = self.mac_y + self.line_height

        self._static_drawn = False
        self._last_rssi = None

    CREATION_PRIORITY = 1
    def create(provider):
        y_separator = provider['config']['display'].get('y_separator', 70)
        return StartupDisplay(provider['display'], provider['nic'], y_separator)

    async def start(self):
        await asyncio.Event().wait()

    def should_activate(self):
        return self.pending_activation

    async def activate(self):
        self.pending_activation = False
        while True:
            await self.update()
            await asyncio.sleep(0.1)

    async def _draw_static(self):
        # IP Address
        try:
            ip = self.nic.ifconfig()[0]
        except Exception:
            ip = "?"
        await textbox.draw_textbox(self.display, f"IP: {ip}", self.x, self.ip_y, self.width, self.line_height, color=0xFFFFFF, background=0x000000, font='small', align='left')

        # Hostname
        try:
            hostname = self.nic.config('hostname')
        except Exception:
            hostname = "?"
        await textbox.draw_textbox(self.display, f"Host: {hostname}", self.x, self.host_y, self.width, self.line_height, color=0xFFFFFF, background=0x000000, font='small', align='left')

        # SSID
        try:
            ssid = self.nic.config('ssid')
        except Exception:
            ssid = "?"
        await textbox.draw_textbox(self.display, f"WiFi: {ssid}", self.x, self.ssid_y, self.width, self.line_height, color=0xFFFFFF, background=0x000000, font='small', align='left')

        # MAC Address
        try:
            mac_bytes = self.nic.config('mac')
            mac = binascii.hexlify(mac_bytes, ':').decode().upper()
        except Exception:
            mac = "?"
        await textbox.draw_textbox(self.display, f"MAC: {mac}", self.x, self.mac_y, self.width, self.line_height, color=0xFFFFFF, background=0x000000, font='small', align='left')

    async def update(self):
        if not self._static_drawn:
            self._static_drawn = True
            await self._draw_static()

        # Signal strength is the only field that actually changes while active
        try:
            rssi = self.nic.status('rssi')
        except Exception:
            rssi = "?"

        if rssi != self._last_rssi:
            self._last_rssi = rssi
            await textbox.draw_textbox(self.display, f"Signal: {rssi} dBm", self.x, self.signal_y, self.width, self.line_height, color=0xFFFFFF, background=0x000000, font='small', align='left')
