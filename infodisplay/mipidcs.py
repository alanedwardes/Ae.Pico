import os
import micropython
from machine import PWM

# User orientation constants
LANDSCAPE = 0
REFLECT = 1
USD = 2
PORTRAIT = 4

# SPI Hardware Register offsets (common to RP2040/RP2350)
_SPI_SSPDR_OFFSET = 0x08
_SPI_SSPDMACR_OFFSET = 0x24
_SPI_TXDMAE_BIT = 0x02

# Detect chip type for hardware addresses and DREQs
try:
    _machine = os.uname().machine
except:
    _machine = "Unknown"

if "RP2350" in _machine:
    _SPI0_BASE = 0x40080000
    _SPI1_BASE = 0x40088000
    _DREQ_SPI0_TX = 24
    _DREQ_SPI1_TX = 26
elif "RP2040" in _machine:
    _SPI0_BASE = 0x4003c000
    _SPI1_BASE = 0x40040000
    _DREQ_SPI0_TX = 16
    _DREQ_SPI1_TX = 18
else:
    _SPI0_BASE = 0
    _SPI1_BASE = 0
    _DREQ_SPI0_TX = 0
    _DREQ_SPI1_TX = 0

def rgb(r, g, b):
    """Convert r, g, b in range 0-255 to a 16-bit RGB565 colour value."""
    return ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)

def get_madctl(user_mode, panel_orientation, bgr):
    """Calculate MADCTL register value based on orientation and color order."""
    if not panel_orientation:
        user_mode ^= PORTRAIT
    mode_map = (0x60, 0xE0, 0xA0, 0x20, 0x00, 0x40, 0xC0, 0x80)
    madctl = mode_map[user_mode]
    if bgr:
        madctl |= 0x08
    return madctl

def get_window_coords(ram_w, ram_h, win_w, win_h, x_offset, y_offset, mode, x, y, rw, rh):
    """Calculate hardware RAM coordinates for a given window/region."""
    portrait_bit, reflect_bit, usd_bit = 0x20, 0x40, 0x80
    if mode & portrait_bit:
        xo, yo = y_offset, x_offset
        xs = x + xo
        xe = xs + rw - 1
        ys = y + yo
        ye = ys + rh - 1
        if mode & reflect_bit:
            ys = ram_w - win_h - yo + y
            ye = ys + rh - 1
        if mode & usd_bit:
            xs = ram_h - win_w - xo + x
            xe = xs + rw - 1
    else:
        xo, yo = x_offset, y_offset
        xs = x + xo
        xe = xs + rw - 1
        ys = y + yo
        ye = ys + rh - 1
        if mode & usd_bit:
            ys = ram_h - win_h - yo + y
            ye = ys + rh - 1
        if mode & reflect_bit:
            xs = ram_w - win_w - xo + x
            xe = xs + rw - 1
    return xs, xe, ys, ye

class BacklightManager:
    def __init__(self, pin):
        self._pin = pin
        self._pwm = None

    def set(self, brightness):
        """Set backlight brightness from 0.0 to 1.0."""
        if self._pin is None:
            return
        brightness = max(0.0, min(1.0, float(brightness)))
        if self._pwm is not None:
            self._pwm.duty_u16(int(brightness * 65535))
            return
        if brightness == 0.0:
            self._pin.value(0)
        elif brightness == 1.0:
            self._pin.value(1)
        else:
            self._pwm = PWM(self._pin)
            self._pwm.freq(1000)
            self._pwm.duty_u16(int(brightness * 65535))

class SpiController:
    def __init__(self, spi, dc, cs):
        self.spi = spi
        self.dc = dc
        self.cs = cs

    def write_cmd(self, cmd):
        self.cs(1)
        self.dc(0)
        self.cs(0)
        self.spi.write(cmd)
        self.cs(1)

    def write_cd(self, c, d):
        """Write command followed by data."""
        self.cs(1)
        self.dc(0)
        self.cs(0)
        self.spi.write(c)
        self.cs(1)
        for byte in d:
            self.dc(1)
            self.cs(0)
            self.spi.write(bytearray([byte]))
            self.cs(1)

    def write_data(self, d):
        """Write raw data (usually coordinates for window set)."""
        for byte in d:
            self.dc(1)
            self.cs(0)
            self.spi.write(bytearray([byte]))
            self.cs(1)

    def start_data(self):
        """Start a bulk data transfer (RAMWR)."""
        self.dc(1)
        self.cs(0)

    def end_data(self):
        """End a bulk data transfer."""
        self.cs(1)

    def clear(self, width, height, linebuf):
        """Clear the entire display using the provided line buffer."""
        self.write_cmd(b"\x2c") # RAMWR
        self.start_data()
        for i in range(len(linebuf)):
            linebuf[i] = 0
        for _ in range(height):
            self.spi.write(linebuf)
        self.end_data()

class DmaManager:
    def __init__(self, spi, width, spi_id, bytes_per_pixel=3):
        self._spi = spi
        self._width = width
        self._bytes_per_pixel = bytes_per_pixel
        self._dma = None
        self._spi_dr = 0
        self._linebuf_pair = [bytearray(width * bytes_per_pixel), bytearray(width * bytes_per_pixel)]
        self._linebuf_idx = 0
        self._ctrl = None

        if _SPI0_BASE != 0:
            try:
                import rp2
                self._setup_dma(spi_id)
            except ImportError:
                pass

    def _setup_dma(self, spi_id):
        if spi_id == 0:
            base, dreq = _SPI0_BASE, _DREQ_SPI0_TX
        elif spi_id == 1:
            base, dreq = _SPI1_BASE, _DREQ_SPI1_TX
        else:
            return

        self._spi_dr = base + _SPI_SSPDR_OFFSET
        dmacr = base + _SPI_SSPDMACR_OFFSET
        
        @micropython.viper
        def _enable_spi_dma(addr: int, bit: int):
            p = ptr32(addr)
            p[0] |= bit
        _enable_spi_dma(dmacr, _SPI_TXDMAE_BIT)
        
        import rp2
        self._dma = rp2.DMA()
        self._ctrl = self._dma.pack_ctrl(size=0, inc_read=True, inc_write=False, treq_sel=dreq)

    @property
    def active(self):
        return self._dma is not None

    def get_next_buffer(self):
        buf = self._linebuf_pair[self._linebuf_idx]
        self._linebuf_idx = (self._linebuf_idx + 1) & 1
        return buf

    def send(self, buf, count=None):
        if not self._dma:
            self._spi.write(buf)
            return

        if count is None:
            count = len(buf)

        while self._dma.active():
            pass
        
        self._dma.config(
            read=buf,
            write=self._spi_dr,
            count=count,
            ctrl=self._ctrl,
            trigger=True
        )

    def wait(self):
        if self._dma:
            while self._dma.active():
                pass
