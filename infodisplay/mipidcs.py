import micropython

try:
    from machine import PWM
except ImportError:
    PWM = None

try:
    import rp2
    import time
    from machine import mem32
    _HAS_RP2_DMA = hasattr(rp2, 'DMA')
except ImportError:
    _HAS_RP2_DMA = False

# PL022 SPI block (base address, TX DREQ) per SPI id, keyed by chip
_SPI_TX_DMA_MAP = {
    'RP2350': {0: (0x40080000, 24), 1: (0x40088000, 26)},
    'RP2040': {0: (0x4003c000, 16), 1: (0x40040000, 18)},
}

# User orientation constants
LANDSCAPE = 0
REFLECT = 1
USD = 2
PORTRAIT = 4

# --- Viper Converters (Shared) ---

@micropython.viper
def _rgb565_to_888_line(dest: ptr8, source: ptr16, src_offset: int, pixels: int, lut: ptr8):
    # For RGB565 to RGB666 (3 bytes per pixel) - Unrolled 4x for speed + LUT
    s: int = src_offset
    d: int = 0
    while pixels >= 4:
        c = source[s]
        dest[d] = lut[(c >> 11) & 0x1F]
        dest[d + 1] = lut[((c >> 5) & 0x3F) + 32]
        dest[d + 2] = lut[(c & 0x1F) + 96]
        c = source[s + 1]
        dest[d + 3] = lut[(c >> 11) & 0x1F]
        dest[d + 4] = lut[((c >> 5) & 0x3F) + 32]
        dest[d + 5] = lut[(c & 0x1F) + 96]
        c = source[s + 2]
        dest[d + 6] = lut[(c >> 11) & 0x1F]
        dest[d + 7] = lut[((c >> 5) & 0x3F) + 32]
        dest[d + 8] = lut[(c & 0x1F) + 96]
        c = source[s + 3]
        dest[d + 9] = lut[(c >> 11) & 0x1F]
        dest[d + 10] = lut[((c >> 5) & 0x3F) + 32]
        dest[d + 11] = lut[(c & 0x1F) + 96]
        s += 4; d += 12; pixels -= 4
    while pixels:
        c = source[s]
        dest[d] = lut[(c >> 11) & 0x1F]
        dest[d + 1] = lut[((c >> 5) & 0x3F) + 32]
        dest[d + 2] = lut[(c & 0x1F) + 96]
        s += 1; d += 3; pixels -= 1

@micropython.viper
def _rgb565_to_888_upscale_line(dest: ptr8, source: ptr16, src_offset: int, src_pixels: int, scale: int, lut: ptr8):
    s: int = src_offset
    d: int = 0
    while src_pixels:
        c = source[s]
        r8 = lut[(c >> 11) & 0x1F]
        g8 = lut[((c >> 5) & 0x3F) + 32]
        b8 = lut[(c & 0x1F) + 96]
        for _ in range(scale):
            dest[d] = r8; dest[d + 1] = g8; dest[d + 2] = b8
            d += 3
        s += 1; src_pixels -= 1

@micropython.viper
def _rgb565_swap_line(dest: ptr16, source: ptr16, src_offset: int, pixels: int, lut: ptr8):
    # For RGB565 byte swap - Unrolled 4x
    s: int = src_offset
    d: int = 0
    while pixels >= 4:
        c = source[s]; dest[d] = (c << 8) | (c >> 8)
        c = source[s+1]; dest[d+1] = (c << 8) | (c >> 8)
        c = source[s+2]; dest[d+2] = (c << 8) | (c >> 8)
        c = source[s+3]; dest[d+3] = (c << 8) | (c >> 8)
        s += 4; d += 4; pixels -= 4
    while pixels:
        c = source[s]; dest[d] = (c << 8) | (c >> 8)
        s += 1; d += 1; pixels -= 1

@micropython.viper
def _rgb565_swap_upscale_line(dest: ptr16, source: ptr16, src_offset: int, src_pixels: int, scale: int, lut: ptr8):
    s: int = src_offset
    d: int = 0
    while src_pixels:
        c = source[s]
        sw = (c << 8) | (c >> 8)
        for _ in range(scale):
            dest[d] = sw
            d += 1
        s += 1; src_pixels -= 1

def build_rgb332_888_lut():
    """256-entry RGB332 -> RGB888 table (768 bytes) for _rgb332_to_888_line."""
    lut = bytearray(256 * 3)
    for c in range(256):
        lut[c * 3] = (c & 0xe0) | ((c & 0xe0) >> 3) | ((c & 0xe0) >> 6)
        lut[c * 3 + 1] = ((c << 3) & 0xe0) | (c & 0x1c) | ((c >> 3) & 0x03)
        lut[c * 3 + 2] = ((c << 6) & 0xc0) | ((c << 4) & 0x30) | ((c << 2) & 0x0c) | (c & 0x03)
    return lut

@micropython.viper
def _rgb332_to_888_line(dest: ptr8, source: ptr8, src_offset: int, pixels: int, lut: ptr8):
    # lut must be the 768-byte table from build_rgb332_888_lut - Unrolled 4x
    s: int = src_offset
    d: int = 0
    while pixels >= 4:
        i: int = source[s] * 3
        dest[d] = lut[i]; dest[d + 1] = lut[i + 1]; dest[d + 2] = lut[i + 2]
        i = source[s + 1] * 3
        dest[d + 3] = lut[i]; dest[d + 4] = lut[i + 1]; dest[d + 5] = lut[i + 2]
        i = source[s + 2] * 3
        dest[d + 6] = lut[i]; dest[d + 7] = lut[i + 1]; dest[d + 8] = lut[i + 2]
        i = source[s + 3] * 3
        dest[d + 9] = lut[i]; dest[d + 10] = lut[i + 1]; dest[d + 11] = lut[i + 2]
        s += 4; d += 12; pixels -= 4
    while pixels:
        i2: int = source[s] * 3
        dest[d] = lut[i2]; dest[d + 1] = lut[i2 + 1]; dest[d + 2] = lut[i2 + 2]
        s += 1; d += 3; pixels -= 1

@micropython.viper
def _rgb332_to_565_line(dest: ptr8, source: ptr8, src_offset: int, pixels: int, lut: ptr8):
    s: int = src_offset
    d: int = 0
    while pixels >= 4:
        idx: int = source[s] << 1
        dest[d] = lut[idx]; dest[d+1] = lut[idx+1]
        idx = source[s+1] << 1
        dest[d+2] = lut[idx]; dest[d+3] = lut[idx+1]
        idx = source[s+2] << 1
        dest[d+4] = lut[idx]; dest[d+5] = lut[idx+1]
        idx = source[s+3] << 1
        dest[d+6] = lut[idx]; dest[d+7] = lut[idx+1]
        s += 4; d += 8; pixels -= 4
    while pixels:
        idx: int = source[s] << 1
        dest[d] = lut[idx]; dest[d+1] = lut[idx+1]
        s += 1; d += 2; pixels -= 1

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

class _SpiTxDma:
    """DREQ-paced DMA from memory into an SPI TX FIFO.

    The SPI peripheral throttles the DMA channel, so the panel sees
    ordinary SPI waveforms. Raises on any board where the SPI block or
    DREQ cannot be verified, so callers can fall back to blocking writes.
    """
    def __init__(self, spi):
        import os
        machine_name = os.uname().machine
        for chip in _SPI_TX_DMA_MAP:
            if chip in machine_name:
                break
        else:
            raise OSError('unrecognised chip: ' + machine_name)
        spi_id = int(str(spi).split('(', 1)[1].split(',', 1)[0])
        base, dreq = _SPI_TX_DMA_MAP[chip][spi_id]
        # ARM PL022 identity registers guard against a wrong base address
        if (mem32[base + 0xFE0] & 0xFF) != 0x22 or (mem32[base + 0xFE4] & 0xFF) != 0x10:
            raise OSError('not a PL022 SPI block')
        self._dr = base + 0x008  # SSPDR
        self._sr = base + 0x00C  # SSPSR (bit 4 = BSY)
        self._dma = rp2.DMA()
        self._ctrl = self._dma.pack_ctrl(size=0, inc_read=True, inc_write=False, treq_sel=dreq)
        try:
            # Self-test: a wrong DREQ never fires and the transfer stalls
            self.start(b'\x00' * 8, 8)
            t0 = time.ticks_us()
            while self._dma.active():
                if time.ticks_diff(time.ticks_us(), t0) > 20000:
                    self._dma.active(0)
                    raise OSError('SPI TX DREQ did not pace DMA')
            while mem32[self._sr] & 0x10:  # let the test bytes leave the wire
                pass
        except Exception:
            self._dma.close()
            raise

    def start(self, buf, length):
        self._dma.config(read=buf, write=self._dr, count=length, ctrl=self._ctrl, trigger=True)

    def wait(self):
        while self._dma.active():
            pass

class SpiController:
    def __init__(self, spi, dc, cs, chunked_data=True):
        self.spi = spi
        self.dc = dc
        self.cs = cs
        self.chunked_data = chunked_data
        self._byte_buf = bytearray(1)

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
        if self.chunked_data:
            for byte in d:
                self.dc(1)
                self.cs(0)
                self._byte_buf[0] = byte
                self.spi.write(self._byte_buf)
                self.cs(1)
        else:
            self.dc(1)
            self.cs(0)
            self.spi.write(d)
            self.cs(1)

    def write_data(self, d):
        """Write raw data (usually coordinates for window set)."""
        if self.chunked_data:
            for byte in d:
                self.dc(1)
                self.cs(0)
                self._byte_buf[0] = byte
                self.spi.write(self._byte_buf)
                self.cs(1)
        else:
            self.dc(1)
            self.cs(0)
            self.spi.write(d)
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

class MipiDisplay:
    """Base class for MIPI DCS compatible displays (ILI9488, ST7789, etc)."""
    def __init__(self, spi, cs, dc, backlight, width, height, scale, color_mode, bpp, chunked_command_data=True):
        self._spi = spi
        self._cs = cs
        self._dc = dc
        self._backlight = BacklightManager(backlight)
        self.width = width
        self.height = height
        self._scale = scale
        self.source_color_mode = color_mode
        self._bpp = bpp # Bytes per pixel on SPI bus
        self._linebuf = bytearray(width * bpp)
        self._cmd_buf = bytearray(4)
        self._lut = None # To be initialized by subclass

        self._spi_ctrl = SpiController(spi, dc, cs, chunked_data=chunked_command_data)

        self._spi_dma = None
        self._linebuf2 = None
        if _HAS_RP2_DMA:
            try:
                self._spi_dma = _SpiTxDma(spi)
                self._linebuf2 = bytearray(width * bpp)
            except Exception:
                self._spi_dma = None

        self._ram_w = width
        self._ram_h = height

    def _window_coords(self, mode, x, y, rw, rh):
        ram_w = int(self._ram_w); ram_h = int(self._ram_h)
        win_w = int(self.width); win_h = int(self.height)
        xo, yo = self._offset
        portrait_bit, reflect_bit, usd_bit = 0x20, 0x40, 0x80
        if mode & portrait_bit:
            xo, yo = yo, xo
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

    def render(self, fb, width, height, bbox):
        x, y, rw, rh = bbox
        if x < 0 or y < 0 or rw <= 0 or rh <= 0: return
        if x + rw > width or y + rh > height: return
            
        scale = self._scale
        self._set_region_window(x * scale, y * scale, rw * scale, rh * scale)
        self._spi_ctrl.write_cmd(b"\x2c")  # RAMWR
        self._spi_ctrl.start_data()
        
        line_conv = self._get_line_conv(scale)
        fb_ptr = y * width + x
        lut = self._lut
        bpp = self._bpp
        
        self._render_spi(fb, width, fb_ptr, rw, rh, scale, bpp, lut, line_conv)
        self._spi_ctrl.end_data()



    def _render_spi(self, fb, width, fb_ptr, rw, rh, scale, bpp, lut, line_conv):
        write_len = rw * scale * bpp
        out_view = memoryview(self._linebuf)[:write_len]
        if scale > 1:
            for _ in range(rh):
                lb = self._linebuf
                line_conv(lb, fb, fb_ptr, rw, scale, lut)
                fb_ptr += width
                for _ in range(scale):
                    self._spi.write(out_view)
            return

        dma = self._spi_dma
        if dma is not None and rh > 1:
            # Double-buffered: DMA line N to the panel while converting
            # line N+1. The final line goes through blocking spi.write,
            # which drains the FIFO and BSY so end_data() can raise CS.
            buf_a = self._linebuf
            buf_b = self._linebuf2
            line_conv(buf_a, fb, fb_ptr, rw, lut)
            fb_ptr += width
            for _ in range(rh - 1):
                dma.start(buf_a, write_len)
                line_conv(buf_b, fb, fb_ptr, rw, lut)
                fb_ptr += width
                dma.wait()
                buf_a, buf_b = buf_b, buf_a
            if buf_a is not self._linebuf:
                out_view = memoryview(buf_a)[:write_len]
            self._spi.write(out_view)
            return

        for _ in range(rh):
            lb = self._linebuf
            line_conv(lb, fb, fb_ptr, rw, lut)
            fb_ptr += width
            self._spi.write(out_view)

    def _get_line_conv(self, scale):
        raise NotImplementedError

    def _set_region_window(self, x, y, rw, rh):
        raise NotImplementedError

    def _wcmd(self, buf):
        self._spi_ctrl.write_cmd(buf)

    def _wcd(self, c, d):
        self._spi_ctrl.write_cd(c, d)

    def _wcd_data(self, d):
        self._spi_ctrl.write_data(d)

    def set_rotation_degrees(self, degrees):
        deg = degrees % 360
        if deg == 0:
            mode = LANDSCAPE
        elif deg == 90:
            mode = PORTRAIT
        elif deg == 180:
            mode = LANDSCAPE | USD
        elif deg == 270:
            mode = PORTRAIT | REFLECT
        else:
            raise ValueError("Degrees must be one of 0, 90, 180, 270")
        self.set_rotation(mode)

    def set_backlight(self, brightness):
        self._backlight.set(brightness)
