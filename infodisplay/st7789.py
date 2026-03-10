from time import sleep_ms
import gc
import micropython
from mipidcs import LANDSCAPE, REFLECT, USD, PORTRAIT, rgb, get_madctl, get_window_coords, MipiDisplay, \
    _rgb565_swap_line, _rgb565_swap_upscale_line, _rgb332_to_565_line

# Display types
GENERIC = (0, 0, 1, 0, True) # Default (x, y, orientation, bgr, inv)
TDISPLAY = 0x342801
PI_PICO_LCD_2 = 0x000001
DFR0995 = 0x220000
WAVESHARE_13 = 0x000010
ADAFRUIT_1_9 = (35, 0, PORTRAIT)

class ST7789(MipiDisplay):
    rgb = staticmethod(rgb)

    def __init__(self, spi, cs, dc, backlight=None, height=240, width=240, 
                 disp_mode=LANDSCAPE, init_spi=False, display=GENERIC, 
                 spi_id=0, scale=1, source_color_mode='RGB565', use_dma=None):
        
        super().__init__(spi, cs, dc, backlight, width, height, scale, source_color_mode, 2, spi_id, use_dma)
        
        self._offset = display[:2]
        self._spi_init = init_spi
        
        # Initialize RGB332 to 565 LUT (512 bytes)
        self._lut = bytearray(512)
        for i in range(256):
            r3 = (i >> 5) & 0x07; g3 = (i >> 2) & 0x07; b2 = i & 0x03
            r5 = (r3 << 2) | (r3 >> 1); g6 = (g3 << 3) | g3; b5 = (b2 << 3) | (b2 << 1) | (b2 >> 1)
            self._lut[i*2] = (r5 << 3) | (g6 >> 3)      # hi
            self._lut[i*2 + 1] = ((g6 & 0x07) << 5) | b5 # lo
            
        self._init(disp_mode, display[2], display[3:])

    def _get_line_conv(self, scale):
        if self.source_color_mode == 'RGB565':
            return _rgb565_swap_line if scale == 1 else _rgb565_swap_upscale_line
        return _rgb332_to_565_line 

    def _init(self, user_mode, orientation, cfg):
        bgr = cfg[0] if len(cfg) else False
        inv = cfg[1] if len(cfg) else False
        self._bgr = bgr
        self._orientation = orientation
        if self._spi_init: self._spi_init(self._spi)
        
        self._wcmd(b"\x01"); sleep_ms(150)
        self._wcmd(b"\x11"); sleep_ms(10)
        self._wcd(b"\x3a", b"\x55") # _COLMOD 16 bit
        self._wcmd(b"\x21" if inv else b"\x20")
        self._wcmd(b"\x13") # NORON
        
        mode = get_madctl(user_mode, orientation, bgr)
        self._current_mode = mode
        self.set_window(mode)
        self._wcd(b"\x36", int.to_bytes(mode, 1, "little"))
        self._spi_ctrl.clear(self.width, self.height, self._linebuf)
        self._wcmd(b"\x29") # DISPON

    def _wcmd(self, buf): self._spi_ctrl.write_cmd(buf)
    def _wcd(self, c, d):
        self._dc(0); self._cs(0); self._spi.write(c); self._cs(1)
        self._dc(1); self._cs(0); self._spi.write(d); self._cs(1)

    def set_rotation(self, disp_mode):
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