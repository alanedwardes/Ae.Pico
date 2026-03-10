# Forked from https://github.com/peterhinch/micropython-micro-gui/blob/main/drivers/st7789/st7789_8bit.py
from time import sleep_ms
import gc
import micropython
from machine import PWM
from mipidcs import LANDSCAPE, REFLECT, USD, PORTRAIT, rgb, get_madctl, get_window_coords, BacklightManager, SpiController, DmaManager

# Display types
GENERIC = (0, 0, 1, 0, True) # Default (x, y, orientation, bgr, inv)
TDISPLAY = 0x342801
PI_PICO_LCD_2 = 0x000001  # Waveshare Pico LCD 2 determined by Mike Wilson.
DFR0995 = 0x220000  # DFR0995 Contributed by @EdgarKluge
WAVESHARE_13 = 0x000010  # Waveshare 1.3" 240x240 LCD contributed by Aaron Mittelmeier
ADAFRUIT_1_9 = (35, 0, PORTRAIT)  #  320x170 TFT https://www.adafruit.com/product/5394

@micropython.viper
def _swapline(dest: ptr16, source: ptr16, src_offset: int, pixels: int, lut: ptr8):
    # For RGB565 mode (2 bytes per pixel) - Unrolled 4x for speed
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
def _upscale_line(dest: ptr16, source: ptr16, src_offset: int, src_pixels: int, scale: int, lut: ptr8):
    # For RGB565 mode upscale
    s: int = src_offset
    d: int = 0
    while src_pixels:
        c = source[s]
        swapped = (c << 8) | (c >> 8)
        for _ in range(scale):
            dest[d] = swapped
            d += 1
        s += 1; src_pixels -= 1

@micropython.viper
def _rgb332_to_565_line(dest: ptr8, source: ptr8, src_offset: int, pixels: int, lut: ptr8):
    """Convert RGB332 (1 byte/pixel) to byte-swapped RGB565 (2 bytes/pixel) via LUT."""
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

@micropython.viper
def _rgb332_to_565_upscale_line(dest: ptr8, source: ptr8, src_offset: int, src_pixels: int, scale: int, lut: ptr8):
    """Convert RGB332 to byte-swapped RGB565 with horizontal upscaling via LUT."""
    s: int = src_offset
    d: int = 0
    while src_pixels:
        idx: int = source[s] << 1
        hi = lut[idx]; lo = lut[idx+1]
        for _ in range(scale):
            dest[d] = hi; dest[d+1] = lo
            d += 2
        s += 1; src_pixels -= 1

class ST7789:
    rgb = staticmethod(rgb)

    def __init__(
        self,
        spi,
        cs,
        dc,
        backlight=None,
        height=240,
        width=240,
        disp_mode=LANDSCAPE,
        init_spi=False,
        display=GENERIC,
        spi_id=0,
        scale=1,
        source_color_mode='RGB565',
        use_dma=None,
    ):
        if not 0 <= disp_mode <= 7:
            raise ValueError("Invalid display mode:", disp_mode)
        self._spi = spi
        self._dc = dc
        self._cs = cs
        self._backlight = BacklightManager(backlight)
        self._scale = scale
        self.height = height
        self.width = width
        self._offset = display[:2]
        orientation = display[2]
        self._spi_init = init_spi
        self.source_color_mode = source_color_mode
        gc.collect()
        self._linebuf = bytearray(self.width * 2)
        
        # Initialize RGB332 to 565 LUT (512 bytes)
        self._lut = bytearray(512)
        for i in range(256):
            r3 = (i >> 5) & 0x07; g3 = (i >> 2) & 0x07; b2 = i & 0x03
            r5 = (r3 << 2) | (r3 >> 1); g6 = (g3 << 3) | g3; b5 = (b2 << 3) | (b2 << 1) | (b2 >> 1)
            self._lut[i*2] = (r5 << 3) | (g6 >> 3)      # hi
            self._lut[i*2 + 1] = ((g6 & 0x07) << 5) | b5 # lo

        self._spi_ctrl = SpiController(spi, dc, cs)
        self._dma = DmaManager(spi, self.width, spi_id=spi_id, bytes_per_pixel=2, use_dma=use_dma)

        self._init(disp_mode, orientation, display[3:])

    def _wcmd(self, buf):
        self._spi_ctrl.write_cmd(buf)

    def _wcd(self, c, d):
        # ST7789 doesn't need the per-byte CS cycle like ILI9488
        self._dc(0)
        self._cs(0)
        self._spi.write(c)
        self._cs(1)
        self._dc(1)
        self._cs(0)
        self._spi.write(d)
        self._cs(1)

    def _init(self, user_mode, orientation, cfg):
        bgr = cfg[0] if len(cfg) else False
        inv = cfg[1] if len(cfg) else False
        self._bgr = bgr
        self._orientation = orientation
        if self._spi_init:
            self._spi_init(self._spi)
        cmd = self._wcmd
        wcd = self._wcd
        cmd(b"\x01")  # SW reset
        sleep_ms(150)
        cmd(b"\x11")  # SLPOUT
        sleep_ms(10)
        wcd(b"\x3a", b"\x55")  # _COLMOD 16 bit
        cmd(b"\x21" if inv else b"\x20")
        cmd(b"\x13")  # NORON
        mode = get_madctl(user_mode, orientation, bgr)
        self._current_mode = mode
        self.set_window(mode)
        wcd(b"\x36", int.to_bytes(mode, 1, "little"))
        self._clear_display()
        cmd(b"\x29")  # DISPON

    def _clear_display(self):
        self._spi_ctrl.clear(self.width, self.height, self._linebuf)

    def set_rotation(self, disp_mode):
        if not 0 <= disp_mode <= 7:
            raise ValueError("Invalid display mode:", disp_mode)
        mode = get_madctl(disp_mode, self._orientation, self._bgr)
        self._current_mode = mode
        self.set_window(mode)
        self._wcd(b"\x36", int.to_bytes(mode, 1, "little"))

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

    def set_window(self, mode):
        # ST7789 RAM is (typically) 240x320
        xs, xe, ys, ye = get_window_coords(240, 320, self.width, self.height, self._offset[0], self._offset[1], mode, 0, 0, self.width, self.height)
        self._wcd(b"\x2a", int.to_bytes((xs << 16) + xe, 4, "big"))
        self._wcd(b"\x2b", int.to_bytes((ys << 16) + ye, 4, "big"))

    def _set_region_window(self, x, y, rw, rh):
        xs, xe, ys, ye = get_window_coords(240, 320, self.width, self.height, self._offset[0], self._offset[1], self._current_mode, x, y, rw, rh)
        self._wcd(b"\x2a", int.to_bytes((xs << 16) + xe, 4, "big"))
        self._wcd(b"\x2b", int.to_bytes((ys << 16) + ye, 4, "big"))

    def render(self, framebuffer, width, height, region):
        x, y, rw, rh = region
        if x < 0 or y < 0 or rw <= 0 or rh <= 0: return
        if x + rw > width or y + rh > height: return
            
        scale = self._scale
        self._set_region_window(x * scale, y * scale, rw * scale, rh * scale)

        if self._spi_init: self._spi_init(self._spi)
        self._spi_ctrl.write_cmd(b"\x2c") # RAMWR
        self._spi_ctrl.start_data()

        src = memoryview(framebuffer)
        lut = self._lut
        
        if self.source_color_mode == 'RGB565':
            line_conv = _swapline if scale == 1 else _upscale_line
            fb_ptr = y * width + x
            if self._dma.active:
                for row in range(rh):
                    buf = self._dma.get_next_buffer()
                    if scale == 1:
                        line_conv(buf, src, fb_ptr, rw, lut)
                    else:
                        line_conv(buf, src, fb_ptr, rw, scale, lut)
                    fb_ptr += width
                    for _ in range(scale):
                        self._dma.send(buf, count=rw * scale * 2)
                self._dma.wait()
            else:
                for row in range(rh):
                    lb = memoryview(self._linebuf[:rw * scale * 2])
                    if scale == 1:
                        line_conv(lb, src, fb_ptr, rw, lut)
                    else:
                        line_conv(lb, src, fb_ptr, rw, scale, lut)
                    fb_ptr += width
                    for _ in range(scale):
                        self._spi.write(lb)
        else: # RGB332
            line_conv = _rgb332_to_565_line if scale == 1 else _rgb332_to_565_upscale_line
            fb_ptr = y * width + x
            if self._dma.active:
                for row in range(rh):
                    buf = self._dma.get_next_buffer()
                    if scale == 1:
                        line_conv(buf, src, fb_ptr, rw, lut)
                    else:
                        line_conv(buf, src, fb_ptr, rw, scale, lut)
                    fb_ptr += width
                    for _ in range(scale):
                        self._dma.send(buf, count=rw * scale * 2)
                self._dma.wait()
            else:
                for row in range(rh):
                    lb = memoryview(self._linebuf[:rw * scale * 2])
                    if scale == 1:
                        line_conv(lb, src, fb_ptr, rw, lut)
                    else:
                        line_conv(lb, src, fb_ptr, rw, scale, lut)
                    fb_ptr += width
                    for _ in range(scale):
                        self._spi.write(lb)
        self._spi_ctrl.end_data()

    def set_backlight(self, brightness):
        """Set backlight brightness."""
        self._backlight.set(brightness)