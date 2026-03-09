from time import sleep_ms
import gc
import micropython
from machine import Pin
import os
from mipidcs import LANDSCAPE, REFLECT, USD, PORTRAIT, rgb, get_madctl, get_window_coords, BacklightManager, SpiController, DmaManager

# Display types
GENERIC = 0x000000

@micropython.viper
def _rgb565_to_888_line(dest: ptr8, source: ptr16, src_offset: int, pixels: int):
    # For RGB565 to RGB666 (3 bytes per pixel)
    s: int = src_offset
    d: int = 0
    while pixels:
        c = source[s]
        # RGB565 format: RRRRRGGG GGGBBBBB
        r5 = (c >> 11) & 0x1F
        g6 = (c >> 5) & 0x3F
        b5 = c & 0x1F
        
        # Scale to 8-bit strings
        dest[d] = (r5 << 3) | (r5 >> 2)
        dest[d + 1] = (g6 << 2) | (g6 >> 4)
        dest[d + 2] = (b5 << 3) | (b5 >> 2)
        
        s += 1
        d += 3
        pixels -= 1

@micropython.viper
def _rgb565_to_888_upscale_line(dest: ptr8, source: ptr16, src_offset: int, src_pixels: int, scale: int):
    # For RGB565 to RGB666 upscale (3 bytes per pixel)
    s: int = src_offset
    d: int = 0
    while src_pixels:
        c = source[s]
        r5 = (c >> 11) & 0x1F
        g6 = (c >> 5) & 0x3F
        b5 = c & 0x1F
        
        r8 = (r5 << 3) | (r5 >> 2)
        g8 = (g6 << 2) | (g6 >> 4)
        b8 = (b5 << 3) | (b5 >> 2)
        
        for _ in range(scale):
            dest[d] = r8
            dest[d + 1] = g8
            dest[d + 2] = b8
            d += 3
        s += 1
        src_pixels -= 1

@micropython.viper
def _rgb332_to_888_line(dest: ptr8, source: ptr8, src_offset: int, pixels: int):
    """Convert RGB332 (1 byte/pixel) to RGB666 (3 bytes/pixel)"""
    s: int = src_offset
    d: int = 0
    while pixels:
        c = source[s]
        r = (c & 0xe0) | ((c & 0xe0) >> 3) | ((c & 0xe0) >> 6)
        g = ((c << 3) & 0xe0) | (c & 0x1c) | ((c >> 3) & 0x03)
        b = ((c << 6) & 0xc0) | ((c << 4) & 0x30) | ((c << 2) & 0x0c) | (c & 0x03)
        dest[d] = r
        dest[d + 1] = g
        dest[d + 2] = b
        s += 1
        d += 3
        pixels -= 1


@micropython.viper
def _rgb332_to_888_upscale_line(dest: ptr8, source: ptr8, src_offset: int, src_pixels: int, scale: int):
    """Convert RGB332 to RGB666 with horizontal upscaling."""
    s: int = src_offset
    d: int = 0
    while src_pixels:
        c = source[s]
        r8 = (c & 0xe0) | ((c & 0xe0) >> 3) | ((c & 0xe0) >> 6)
        g8 = ((c << 3) & 0xe0) | (c & 0x1c) | ((c >> 3) & 0x03)
        b8 = ((c << 6) & 0xc0) | ((c << 4) & 0x30) | ((c << 2) & 0x0c) | (c & 0x03)
        
        for _ in range(scale):
            dest[d] = r8
            dest[d + 1] = g8
            dest[d + 2] = b8
            d += 3
        s += 1
        src_pixels -= 1

class ILI9488:
    # Use shared rgb function
    rgb = staticmethod(rgb)

    # rst and cs are active low, SPI is mode 0
    def __init__(self,
                 spi,
                 cs,
                 dc,
                 rst,
                 backlight=None,
                 width=480,
                 height=320,
                 disp_mode=LANDSCAPE,
                 display=GENERIC,
                 spi_id=1,
                 scale=1,
                 source_color_mode='RGB565'):
        self._offset = display[:2]
        orientation = display[2]
        
        self._spi = spi
        self._dc = dc
        self._cs = cs
        self._rst = rst
        self._backlight = BacklightManager(backlight)
        self.width = width
        self.height = height
        self._current_mode = disp_mode
        self._display = display
        self._scale = scale
        self.source_color_mode = source_color_mode
        self._linebuf = bytearray(self.width * 3)
        
        self._spi_ctrl = SpiController(spi, dc, cs)
        self._dma = DmaManager(spi, self.width, spi_id=spi_id, bytes_per_pixel=3)

        self._init(disp_mode, orientation, display[3:])

    # Delegate command methods to SpiController
    def _wcmd(self, buf):
        self._spi_ctrl.write_cmd(buf)

    def _wcd(self, c, d):
        self._spi_ctrl.write_cd(c, d)
        
    def _wcd_data(self, d):
        self._spi_ctrl.write_data(d)

    def _init(self, user_mode, orientation, cfg):
        bgr = cfg[0] if len(cfg) else False  # Color mode BGR/RGB
        inv = cfg[1] if len(cfg) else False
        self._bgr = bgr
        self._orientation = orientation
        
        cmd = self._wcmd
        wcd = self._wcd

        if self._rst:
            self._rst.value(1)
            sleep_ms(5)
            self._rst.value(0)
            sleep_ms(10)
            self._rst.value(1)
            sleep_ms(5)

        cmd(b"\x01")  # Software reset
        sleep_ms(150)
        
        cmd(b"\x21")  # Display inversion ON

        wcd(b"\xC2", b"\x33")
        wcd(b"\xC5", b"\x00\x1e\x80")
        wcd(b"\xB1", b"\xB0")
        
        wcd(b"\xE0", b"\x00\x13\x18\x04\x0F\x06\x3a\x56\x4d\x03\x0a\x06\x30\x3e\x0f")
        wcd(b"\xE1", b"\x00\x13\x18\x01\x11\x06\x38\x34\x4d\x06\x0d\x0b\x31\x37\x0f")

        wcd(b"\x3A", b"\x66")  # COLMOD 18-bit (RGB666)
        
        cmd(b"\x11")  # SLPOUT: exit sleep mode
        sleep_ms(120)
        
        cmd(b"\x29")  # DISPON
        
        wcd(b"\xB6", b"\x00\x62")

        mode = get_madctl(user_mode, orientation, bgr)
        self._current_mode = mode
        wcd(b"\x36", int.to_bytes(mode, 1, "little"))  # MADCTL
        self.set_window(mode)

        self._clear_display()

    def _clear_display(self):
        self._spi_ctrl.clear(self.width, self.height, self._linebuf)

    # Change display rotation at runtime using the same flags as constructor
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
            mode = REFLECT
        elif deg == 90:
            mode = PORTRAIT | REFLECT | USD
        elif deg == 180:
            mode = REFLECT | USD
        elif deg == 270:
            mode = PORTRAIT | REFLECT
        else:
            raise ValueError("Degrees must be one of 0, 90, 180, 270")
        self.set_rotation(mode)

    # Define the mapping between RAM and the display.
    def set_window(self, mode):
        # ILI9488 RAM is 320x480
        xs, xe, ys, ye = get_window_coords(320, 480, self.width, self.height, self._offset[0], self._offset[1], mode, 0, 0, self.width, self.height)
        self._wcmd(b"\x2a")
        self._wcd_data(bytes([(xs >> 8) & 0xFF, xs & 0xFF, (xe >> 8) & 0xFF, xe & 0xFF]))
        self._wcmd(b"\x2b")
        self._wcd_data(bytes([(ys >> 8) & 0xFF, ys & 0xFF, (ye >> 8) & 0xFF, ye & 0xFF]))

    def _set_region_window(self, x, y, rw, rh):
        xs, xe, ys, ye = get_window_coords(320, 480, self.width, self.height, self._offset[0], self._offset[1], self._current_mode, x, y, rw, rh)
        self._wcmd(b"\x2a")
        self._wcd_data(bytes([(xs >> 8) & 0xFF, xs & 0xFF, (xe >> 8) & 0xFF, xe & 0xFF]))
        self._wcmd(b"\x2b")
        self._wcd_data(bytes([(ys >> 8) & 0xFF, ys & 0xFF, (ye >> 8) & 0xFF, ye & 0xFF]))

    def render(self, fb, width, height, bbox):
        """Write a framebuffer region to the display."""
        x, y, rw, rh = bbox
        if x < 0 or y < 0 or rw <= 0 or rh <= 0: return
        if x + rw > width or y + rh > height: return
            
        scale = self._scale
        self._set_region_window(x, y, rw, rh)
        self._wcmd(b"\x2c")  # RAMWR
        self._spi_ctrl.start_data()
        
        if self.source_color_mode == 'RGB565':
            line_conv = _rgb565_to_888_line if scale == 1 else _rgb565_to_888_upscale_line
        else:
            line_conv = _rgb332_to_888_line if scale == 1 else _rgb332_to_888_upscale_line
        
        if self._dma.active:
            for row in range(rh):
                buf = self._dma.get_next_buffer()
                if scale == 1:
                    line_conv(buf, fb, (y + row) * width + x, rw)
                else:
                    line_conv(buf, fb, (y + row) * width + x, rw, scale)
                for _ in range(scale):
                    self._dma.send(buf, count=rw * scale * 3)
            self._dma.wait()
        else:
            for row in range(rh):
                if scale == 1:
                    line_conv(self._linebuf, fb, (y + row) * width + x, rw)
                else:
                    line_conv(self._linebuf, fb, (y + row) * width + x, rw, scale)
                for _ in range(scale):
                    self._spi.write(self._linebuf[:rw * scale * 3])
                    
        self._spi_ctrl.end_data()

    def set_backlight(self, brightness):
        """Set backlight brightness."""
        self._backlight.set(brightness)
