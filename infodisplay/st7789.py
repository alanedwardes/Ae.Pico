# Forked from https://github.com/peterhinch/micropython-micro-gui/blob/main/drivers/st7789/st7789_8bit.py
#
# To write to the framebuffer directly from ffmpeg, you will need to use e.g.:
# -pix_fmt rgb565 (or rgb565le)
#

from time import sleep_ms
import gc
import micropython
from machine import PWM

# User orientation constants
# Waveshare Pico res touch defaults to portrait. Requires PORTRAIT for landscape orientation.
LANDSCAPE = 0  # Default
REFLECT = 1
USD = 2
PORTRAIT = 4
# Display types
GENERIC = (0, 0, 0)  # Default. Suits Waveshare Pico res touch.
TDISPLAY = (52, 40, 1)
PI_PICO_LCD_2 = (0, 0, 1)  # Waveshare Pico LCD 2 determined by Mike Wilson.
DFR0995 = (34, 0, 0)  # DFR0995 Contributed by @EdgarKluge
WAVESHARE_13 = (0, 0, 16)  # Waveshare 1.3" 240x240 LCD contributed by Aaron Mittelmeier
ADAFRUIT_1_9 = (35, 0, PORTRAIT)  #  320x170 TFT https://www.adafruit.com/product/5394
# Note a 5-tuple may be passed if colors are wrong. Extra values are boolean
# bgr: True if color is BGR, False is RGB (default)
# inv: True if color mode is inverted, False normal (default)

@micropython.viper
def _swapline(dest: ptr16, source: ptr16, src_offset: int, pixels: int):
    # For RGB565 mode (2 bytes per pixel)
    s: int = src_offset
    d: int = 0
    while pixels:
        c = source[s]
        dest[d] = (c << 8) | (c >> 8)  # Swap bytes: hi-lo to lo-hi
        s += 1
        d += 1
        pixels -= 1

@micropython.viper
def _upscale_line(dest: ptr16, source: ptr16, src_offset: int, src_pixels: int, scale: int):
    # For RGB565 mode upscale
    s: int = src_offset
    d: int = 0
    while src_pixels:
        c = source[s]
        swapped = (c << 8) | (c >> 8)
        for _ in range(scale):
            dest[d] = swapped
            d += 1
        s += 1
        src_pixels -= 1

@micropython.viper
def _rgb332_to_565_line(dest: ptr8, source: ptr8, src_offset: int, pixels: int):
    """Convert RGB332 (1 byte/pixel) to byte-swapped RGB565 (2 bytes/pixel)."""
    s: int = src_offset
    d: int = 0
    while pixels:
        c = source[s]
        # Extract RGB332 components: RRR GGG BB
        r3 = (c >> 5) & 0x07
        g3 = (c >> 2) & 0x07
        b2 = c & 0x03
        # Expand to RGB565 bit depths by replicating MSBs into LSBs
        r5 = (r3 << 2) | (r3 >> 1)           # 3-bit -> 5-bit
        g6 = (g3 << 3) | g3                   # 3-bit -> 6-bit
        b5 = (b2 << 3) | (b2 << 1) | (b2 >> 1)  # 2-bit -> 5-bit
        # RGB565: RRRRRGGG GGGBBBBB -> hi=RRRRRGGG lo=GGGBBBBB
        hi = (r5 << 3) | (g6 >> 3)
        lo = ((g6 & 0x07) << 5) | b5
        # Byte-swap for SPI (ST7789 expects big-endian)
        dest[d] = lo
        dest[d + 1] = hi
        d += 2
        s += 1
        pixels -= 1

@micropython.viper
def _rgb332_to_565_upscale_line(dest: ptr8, source: ptr8, src_offset: int, src_pixels: int, scale: int):
    """Convert RGB332 to byte-swapped RGB565 with horizontal upscaling."""
    s: int = src_offset
    d: int = 0
    while src_pixels:
        c = source[s]
        r3 = (c >> 5) & 0x07
        g3 = (c >> 2) & 0x07
        b2 = c & 0x03
        r5 = (r3 << 2) | (r3 >> 1)
        g6 = (g3 << 3) | g3
        b5 = (b2 << 3) | (b2 << 1) | (b2 >> 1)
        hi = (r5 << 3) | (g6 >> 3)
        lo = ((g6 & 0x07) << 5) | b5
        for _ in range(scale):
            dest[d] = lo
            dest[d + 1] = hi
            d += 2
        s += 1
        src_pixels -= 1

class ST7789:
    # Convert r, g, b in range 0-255 to a 16-bit RGB565 colour value
    @staticmethod
    def rgb(r, g, b):
        return ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)

    # rst and cs are active low, SPI is mode 0
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
        scale=1,
        source_color_mode='RGB565',
    ):
        if not 0 <= disp_mode <= 7:
            raise ValueError("Invalid display mode:", disp_mode)
        self._spi = spi  # Clock cycle time for write 16ns 62.5MHz max (read is 150ns)
        self._dc = dc
        self._cs = cs
        self._backlight = backlight  # Backlight pin
        self._scale = scale  # Upscaling factor (1 = no upscaling)
        self.height = height  # Required by Writer class
        self.width = width
        self._offset = display[:2]  # display arg is (x, y, orientation)
        orientation = display[2]  # where x, y is the RAM offset
        self._spi_init = init_spi  # Possible user callback
        self.source_color_mode = source_color_mode
        gc.collect()
        self._linebuf = bytearray(self.width * 2)
        self._init(disp_mode, orientation, display[3:])
        self._backlight_pwm = None

    # Write a command, a bytes instance (in practice 1 byte).
    def _wcmd(self, buf):
        self._dc(0)
        self._cs(0)
        self._spi.write(buf)
        self._cs(1)

    # Write a command followed by a data arg.
    def _wcd(self, c, d):
        self._dc(0)
        self._cs(0)
        self._spi.write(c)
        self._cs(1)
        self._dc(1)
        self._cs(0)
        self._spi.write(d)
        self._cs(1)

    # Initialise the hardware. Blocks 163ms. Adafruit have various sleep delays
    # where I can find no requirement in the datasheet. I removed them with
    # other redundant code.
    def _init(self, user_mode, orientation, cfg):
        bgr = cfg[0] if len(cfg) else False  # Color mode BGR/RGB
        inv = cfg[1] if len(cfg) else False
        # Persist configuration needed for runtime rotation changes
        self._bgr = bgr
        self._orientation = orientation
        if self._spi_init:  # A callback was passed
            self._spi_init(self._spi)  # Bus may be shared
        cmd = self._wcmd
        wcd = self._wcd
        cmd(b"\x01")  # SW reset datasheet specifies 120ms before SLPOUT
        sleep_ms(150)
        cmd(b"\x11")  # SLPOUT: exit sleep mode
        sleep_ms(10)  # Adafruit delay 500ms (datsheet 5ms)
        wcd(b"\x3a", b"\x55")  # _COLMOD 16 bit/pixel, 65Kbit color space
        # INVOFF Adafruit turn inversion on. This driver fixes .rgb
        cmd(b"\x21" if inv else b"\x20")
        cmd(b"\x13")  # NORON Normal display mode

        # Table maps user request onto hardware values. index values:
        # 0 Normal
        # 1 Reflect
        # 2 USD
        # 3 USD reflect
        # Followed by same for LANDSCAPE
        if not orientation:
            user_mode ^= PORTRAIT
        # Hardware mappings
        # d7..d5 of MADCTL determine rotation/orientation datasheet P124, P231
        # d5 = MV row/col exchange
        # d6 = MX col addr order
        # d7 = MY page addr order
        # LANDSCAPE = 0
        # PORTRAIT = 0x20
        # REFLECT = 0x40
        # USD = 0x80
        mode = (0x60, 0xE0, 0xA0, 0x20, 0, 0x40, 0xC0, 0x80)[user_mode] | (0x08 if bgr else 0)
        # Set display window depending on mode, .height and .width.
        self._current_mode = mode
        self.set_window(mode)
        wcd(b"\x36", int.to_bytes(mode, 1, "little"))
        self._clear_display()
        cmd(b"\x29")  # DISPON. Adafruit then delay 500ms.

    def _clear_display(self):
        self._wcmd(b"\x2c")  # RAMWR
        self._dc(1)
        self._cs(0)
        for i in range(len(self._linebuf)):
            self._linebuf[i] = 0
        for _ in range(self.height):
            self._spi.write(self._linebuf)
        self._cs(1)

    # Change display rotation at runtime using the same flags as constructor
    # disp_mode is a value 0..7 composed from LANDSCAPE|REFLECT|USD|PORTRAIT
    def set_rotation(self, disp_mode):
        if not 0 <= disp_mode <= 7:
            raise ValueError("Invalid display mode:", disp_mode)
        # Map user mode taking panel default orientation into account
        user_mode = disp_mode
        if not self._orientation:
            user_mode ^= PORTRAIT
        mode = (0x60, 0xE0, 0xA0, 0x20, 0, 0x40, 0xC0, 0x80)[user_mode] | (0x08 if self._bgr else 0)
        # Update address window and MADCTL
        self._current_mode = mode
        self.set_window(mode)
        self._wcd(b"\x36", int.to_bytes(mode, 1, "little"))

    # Convenience: set rotation by degrees: 0, 90, 180, 270
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

    # Define the mapping between RAM and the display.
    # Datasheet section 8.12 p124.
    def set_window(self, mode):
        portrait, reflect, usd = 0x20, 0x40, 0x80
        rht = 320
        rwd = 240  # RAM ht and width
        wht = self.height  # Window (framebuf) dimensions.
        wwd = self.width  # In portrait mode wht > wwd
        if mode & portrait:
            xoff = self._offset[1]  # x and y transposed
            yoff = self._offset[0]
            xs = xoff
            xe = wwd + xoff - 1
            ys = yoff  # y start
            ye = wht + yoff - 1  # y end
            if mode & reflect:
                ys = rwd - wht - yoff
                ye = rwd - yoff - 1
            if mode & usd:
                xs = rht - wwd - xoff
                xe = rht - xoff - 1
        else:  # LANDSCAPE
            xoff = self._offset[0]
            yoff = self._offset[1]
            xs = xoff
            xe = wwd + xoff - 1
            ys = yoff  # y start
            ye = wht + yoff - 1  # y end
            if mode & usd:
                ys = rht - wht - yoff
                ye = rht - yoff - 1
            if mode & reflect:
                xs = rwd - wwd - xoff
                xe = rwd - xoff - 1

        # Col address set.
        self._wcd(b"\x2a", int.to_bytes((xs << 16) + xe, 4, "big"))
        # Row address set
        self._wcd(b"\x2b", int.to_bytes((ys << 16) + ye, 4, "big"))

    def _set_region_window(self, x, y, rw, rh):
        """Set the display window to a specific region for partial updates.

        Args:
            x, y: Top-left corner of region in framebuffer coordinates
            rw, rh: Width and height of region in pixels
        """
        mode = self._current_mode
        portrait, reflect, usd = 0x20, 0x40, 0x80
        rht = 320
        rwd = 240  # RAM ht and width
        wht = self.height  # Window (framebuf) dimensions.
        wwd = self.width  # In portrait mode wht > wwd

        if mode & portrait:
            xoff = self._offset[1]  # x and y transposed
            yoff = self._offset[0]
            xs = x + xoff
            xe = xs + rw - 1
            ys = y + yoff
            ye = ys + rh - 1
            if mode & reflect:
                ys = rwd - self.height - yoff + y
                ye = ys + rh - 1
            if mode & usd:
                xs = rht - self.width - xoff + x
                xe = xs + rw - 1
        else:  # LANDSCAPE
            xoff = self._offset[0]
            yoff = self._offset[1]
            xs = x + xoff
            xe = xs + rw - 1
            ys = y + yoff
            ye = ys + rh - 1
            if mode & usd:
                ys = rht - self.height - yoff + y
                ye = ys + rh - 1
            if mode & reflect:
                xs = rwd - self.width - xoff + x
                xe = xs + rw - 1

        # Col address set.
        self._wcd(b"\x2a", int.to_bytes((xs << 16) + xe, 4, "big"))
        # Row address set
        self._wcd(b"\x2b", int.to_bytes((ys << 16) + ye, 4, "big"))

    def render(self, framebuffer, width, height, region):
        # Unpack and validate region (region is in framebuffer coordinates)
        x, y, rw, rh = region
        if x < 0 or y < 0 or rw <= 0 or rh <= 0:
            return
        if x + rw > width or y + rh > height:
            return
        # Check scaled dimensions match display size
        scale = self._scale
        if width * scale != self.width or height * scale != self.height:
            return

        # Set hardware window to scaled region
        self._set_region_window(x * scale, y * scale, rw * scale, rh * scale)

        # Send RAMWR command
        if self._spi_init:
            self._spi_init(self._spi)
        self._dc(0)
        self._cs(0)
        self._spi.write(b"\x2c")
        self._dc(1)

        src = memoryview(framebuffer)
        
        if self.source_color_mode == 'RGB565':
            # Framebuffer is 2 bytes per pixel (RGB565)
            row_bytes = width * 2
            
            if scale == 1:
                # No upscaling, just byte swapping
                output_bytes = rw * 2
                lb = memoryview(self._linebuf[:output_bytes])
                for row in range(rh):
                    fb_byte_offset = (y + row) * row_bytes + x * 2
                    fb_word_offset = fb_byte_offset // 2
                    _swapline(lb, src, fb_word_offset, rw)
                    self._spi.write(lb)
            else:
                # Upscaling with byte swapping
                output_line_bytes = rw * scale * 2
                lb = memoryview(self._linebuf[:output_line_bytes])
                for row in range(rh):
                    fb_byte_offset = (y + row) * row_bytes + x * 2
                    fb_word_offset = fb_byte_offset // 2
                    _upscale_line(lb, src, fb_word_offset, rw, scale)
                    # Write the line 'scale' times for vertical upscaling
                    for _ in range(scale):
                        self._spi.write(lb)
                        
        else: # RGB332
            # Framebuffer is 1 byte per pixel (RGB332)
            row_bytes = width

            if scale == 1:
                # No upscaling - convert RGB332 to RGB565 and byte swap
                output_bytes = rw * 2
                lb = memoryview(self._linebuf[:output_bytes]) if output_bytes < len(self._linebuf) else memoryview(self._linebuf)
                for row in range(rh):
                    fb_offset = (y + row) * row_bytes + x
                    _rgb332_to_565_line(lb, src, fb_offset, rw)
                    self._spi.write(lb)
            else:
                # Upscaling with RGB332 to RGB565 conversion
                output_line_bytes = rw * scale * 2
                lb = memoryview(self._linebuf[:output_line_bytes])
                for row in range(rh):
                    fb_offset = (y + row) * row_bytes + x
                    _rgb332_to_565_upscale_line(lb, src, fb_offset, rw, scale)
                    for _ in range(scale):
                        self._spi.write(lb)
        self._cs(1)

    def set_backlight(self, brightness):
        """Set backlight brightness.
        
        Args:
            brightness (float): Brightness level from 0.0 (off) to 1.0 (full brightness)
        """
        if self._backlight is None:
            return  # No backlight pin configured
            
        # Clamp brightness to valid range (0.0 to 1.0)
        brightness = max(0.0, min(1.0, float(brightness)))
        
        if self._backlight_pwm is not None:
            self._backlight_pwm.duty_u16(int(brightness * 65535))
            return

        if brightness == 0.0:
            # Turn off backlight completely
            self._backlight.value(0)
        elif brightness == 1.0:
            # Full brightness - use digital output
            self._backlight.value(1)
        else:
            # Use PWM for intermediate brightness levels
            self._backlight_pwm = PWM(self._backlight)
            self._backlight_pwm.freq(1000)  # 1kHz PWM frequency
            
            # Convert brightness (0.0-1.0) to duty cycle (0-65535)
            duty = int(brightness * 65535)
            self._backlight_pwm.duty_u16(duty)