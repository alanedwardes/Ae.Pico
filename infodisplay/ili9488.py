from time import sleep_ms
import gc
import micropython
from mipidcs import LANDSCAPE, REFLECT, USD, PORTRAIT, rgb, get_madctl, get_window_coords, MipiDisplay, \
    _rgb565_to_888_line, _rgb565_to_888_upscale_line, _rgb332_to_888_line

# Display types
GENERIC = (0, 0, 1, True, True) # Default (x, y, orientation, bgr, inv)

class ILI9488(MipiDisplay):
    rgb = staticmethod(rgb)

    def __init__(self, spi, cs, dc, rst, backlight=None, width=480, height=320, 
                 disp_mode=LANDSCAPE, display=GENERIC, spi_id=1, scale=1, 
                 source_color_mode='RGB565', use_dma=None):
        
        super().__init__(spi, cs, dc, backlight, width, height, scale, source_color_mode, 3, spi_id, use_dma, chunked_command_data=True)
        
        self._offset = display[:2]
        self._rst = rst
        self._display = display
        
        # Initialize Micro-LUT (128 bytes)
        self._lut = bytearray(128)
        for i in range(32):
            val = (i << 3) | (i >> 2)
            self._lut[i] = val       # R5
            self._lut[i + 96] = val  # B5
        for i in range(64):
            self._lut[i + 32] = (i << 2) | (i >> 4) # G6
            
        self._init(disp_mode, display[2], display[3:])

    def _get_line_conv(self, scale):
        if self.source_color_mode == 'RGB565':
            return _rgb565_to_888_line if scale == 1 else _rgb565_to_888_upscale_line
        return _rgb332_to_888_line # No upscale for 332->888 yet

    def _init(self, user_mode, orientation, cfg):
        bgr = cfg[0] if len(cfg) else False
        inv = cfg[1] if len(cfg) else False
        self._bgr = bgr
        self._orientation = orientation
        
        if self._rst:
            self._rst.value(1); sleep_ms(5); self._rst.value(0); sleep_ms(10); self._rst.value(1); sleep_ms(5)

        self._wcmd(b"\x01"); sleep_ms(150)
        self._wcmd(b"\x21") # Inversion ON
        self._wcd(b"\xC2", b"\x33")
        self._wcd(b"\xC5", b"\x00\x1e\x80")
        self._wcd(b"\xB1", b"\xB0")
        self._wcd(b"\xE0", b"\x00\x13\x18\x04\x0F\x06\x3a\x56\x4d\x03\x0a\x06\x30\x3e\x0f")
        self._wcd(b"\xE1", b"\x00\x13\x18\x01\x11\x06\x38\x34\x4d\x06\x0d\x0b\x31\x37\x0f")
        self._wcd(b"\x3A", b"\x66") # COLMOD 18-bit
        self._wcmd(b"\x11"); sleep_ms(120)
        self._wcmd(b"\x29") # DISPON
        self._wcd(b"\xB6", b"\x00\x62")

        mode = get_madctl(user_mode, orientation, bgr)
        self._current_mode = mode
        self._wcd(b"\x36", int.to_bytes(mode, 1, "little"))
        self.set_window(mode)
        self._spi_ctrl.clear(self.width, self.height, self._linebuf)

    def set_rotation(self, disp_mode):
        mode = get_madctl(disp_mode, self._orientation, self._bgr)
        self._current_mode = mode
        self.set_window(mode)
        self._wcd(b"\x36", int.to_bytes(mode, 1, "little"))

    def set_window(self, mode):
        xs, xe, ys, ye = get_window_coords(320, 480, self.width, self.height, self._offset[0], self._offset[1], mode, 0, 0, self.width, self.height)
        self._cmd_buf[0] = xs >> 8
        self._cmd_buf[1] = xs & 0xFF
        self._cmd_buf[2] = xe >> 8
        self._cmd_buf[3] = xe & 0xFF
        self._wcmd(b"\x2a")
        self._wcd_data(self._cmd_buf)
        
        self._cmd_buf[0] = ys >> 8
        self._cmd_buf[1] = ys & 0xFF
        self._cmd_buf[2] = ye >> 8
        self._cmd_buf[3] = ye & 0xFF
        self._wcmd(b"\x2b")
        self._wcd_data(self._cmd_buf)

    def _set_region_window(self, x, y, rw, rh):
        xs, xe, ys, ye = get_window_coords(320, 480, self.width, self.height, self._offset[0], self._offset[1], self._current_mode, x, y, rw, rh)
        self._cmd_buf[0] = xs >> 8
        self._cmd_buf[1] = xs & 0xFF
        self._cmd_buf[2] = xe >> 8
        self._cmd_buf[3] = xe & 0xFF
        self._wcmd(b"\x2a")
        self._wcd_data(self._cmd_buf)
        
        self._cmd_buf[0] = ys >> 8
        self._cmd_buf[1] = ys & 0xFF
        self._cmd_buf[2] = ye >> 8
        self._cmd_buf[3] = ye & 0xFF
        self._wcmd(b"\x2b")
        self._wcd_data(self._cmd_buf)
