from time import sleep_ms
import gc
import micropython
from machine import PWM

# User orientation constants
LANDSCAPE = 0  # Default
REFLECT = 1
USD = 2
PORTRAIT = 4
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
    """Convert RGB332 (1 byte/pixel) to RGB666 (3 bytes/pixel)."""
    s: int = src_offset
    d: int = 0
    while pixels:
        c = source[s]
        # Extract RGB332 components: RRR GGG BB
        r3 = (c >> 5) & 0x07
        g3 = (c >> 2) & 0x07
        b2 = c & 0x03
        
        # Scale straight to 8-bit colors
        # RRR -> RRRRRRRR
        dest[d]       = (r3 << 5) | (r3 << 2) | (r3 >> 1)
        # GGG -> GGGGGGGG
        dest[d + 1]   = (g3 << 5) | (g3 << 2) | (g3 >> 1)
        # BB -> BBBBBBBB
        dest[d + 2]   = (b2 << 6) | (b2 << 4) | (b2 << 2) | b2
        
        d += 3
        s += 1
        pixels -= 1

@micropython.viper
def _rgb332_to_888_upscale_line(dest: ptr8, source: ptr8, src_offset: int, src_pixels: int, scale: int):
    """Convert RGB332 to RGB666 with horizontal upscaling."""
    s: int = src_offset
    d: int = 0
    while src_pixels:
        c = source[s]
        r3 = (c >> 5) & 0x07
        g3 = (c >> 2) & 0x07
        b2 = c & 0x03
        
        r8 = (r3 << 5) | (r3 << 2) | (r3 >> 1)
        g8 = (g3 << 5) | (g3 << 2) | (g3 >> 1)
        b8 = (b2 << 6) | (b2 << 4) | (b2 << 2) | b2
        
        for _ in range(scale):
            dest[d] = r8
            dest[d + 1] = g8
            dest[d + 2] = b8
            d += 3
        s += 1
        src_pixels -= 1

class ILI9488:
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
        rst=None,
        backlight=None,
        height=320,
        width=480,
        disp_mode=LANDSCAPE,
        init_spi=False,
        display=GENERIC,
        scale=1,
        source_color_mode='RGB565',
    ):
        if not 0 <= disp_mode <= 7:
            raise ValueError("Invalid display mode:", disp_mode)
        self._spi = spi
        self._dc = dc
        self._cs = cs
        self._rst = rst
        self._backlight = backlight  # Backlight pin
        self._scale = scale  # Upscaling factor (1 = no upscaling)
        self.height = height  # Required by Writer class
        self.width = width
        self._offset = display[:2]  # display arg is (x, y, orientation)
        orientation = display[2]  # where x, y is the RAM offset
        self._spi_init = init_spi  # Possible user callback
        self.source_color_mode = source_color_mode
        gc.collect()
        self._linebuf = bytearray(self.width * 3)  # Changed back to 3 bytes per pixel
        self._init(disp_mode, orientation, display[3:])
        self._backlight_pwm = None

    # Write a command, a bytes instance (in practice 1 byte).
    def _wcmd(self, buf):
        self._cs(1)
        self._dc(0)
        self._cs(0)
        self._spi.write(buf)
        self._cs(1)

    # Write a command followed by a data arg.
    def _wcd(self, c, d):
        self._cs(1)
        self._dc(0)
        self._cs(0)
        self._spi.write(c)
        self._cs(1)
        # Send each data byte with its own CS cycle (matches reference)
        for byte in d:
            self._dc(1)
            self._cs(0)
            self._spi.write(bytearray([byte]))
            self._cs(1)
        
    # Write just data
    def _wcd_data(self, d):
        # Send each data byte with its own CS cycle (matches reference)
        for byte in d:
            self._dc(1)
            self._cs(0)
            self._spi.write(bytearray([byte]))
            self._cs(1)

    def _init(self, user_mode, orientation, cfg):
        bgr = cfg[0] if len(cfg) else False  # Color mode BGR/RGB
        inv = cfg[1] if len(cfg) else False
        # Persist configuration needed for runtime rotation changes
        self._bgr = bgr
        self._orientation = orientation
        
        # Power and timing controls based strictly on Waveshare main_3inch5.py
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

        mode = (0x60, 0xE0, 0xA0, 0x20, 0, 0x40, 0xC0, 0x80)[user_mode] | (0x08 if bgr else 0)
        self._current_mode = mode
        wcd(b"\x36", int.to_bytes(mode, 1, "little"))  # MADCTL
        self.set_window(mode)

        self._clear_display()

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
        portrait, reflect, usd = 0x20, 0x40, 0x80
        rht = 480
        rwd = 320  # RAM ht and width
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

        # Col address set (0x2A)
        self._wcmd(b"\x2a")
        self._wcd_data(bytes([(xs >> 8) & 0xFF, xs & 0xFF, (xe >> 8) & 0xFF, xe & 0xFF]))
        # Row address set (0x2B)
        self._wcmd(b"\x2b")
        self._wcd_data(bytes([(ys >> 8) & 0xFF, ys & 0xFF, (ye >> 8) & 0xFF, ye & 0xFF]))

    def _set_region_window(self, x, y, rw, rh):
        """Set the display window to a specific region for partial updates.

        Args:
            x, y: Top-left corner of region in framebuffer coordinates
            rw, rh: Width and height of region in pixels
        """
        mode = self._current_mode
        portrait, reflect, usd = 0x20, 0x40, 0x80
        rht = 480
        rwd = 320  # RAM ht and width
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

        # Col address set (0x2A)
        self._wcmd(b"\x2a")
        self._wcd_data(bytes([(xs >> 8) & 0xFF, xs & 0xFF, (xe >> 8) & 0xFF, xe & 0xFF]))
        # Row address set (0x2B)
        self._wcmd(b"\x2b")
        self._wcd_data(bytes([(ys >> 8) & 0xFF, ys & 0xFF, (ye >> 8) & 0xFF, ye & 0xFF]))

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

        # Send RAMWR command (0x2C)
        if self._spi_init:
            self._spi_init(self._spi)

        self._wcmd(b"\x2c")
        
        # Prepare for data write (match Waveshare `write_data` and `show_up` flow)
        self._cs(1)
        self._dc(1)
        self._cs(0)

        src = memoryview(framebuffer)
        
        if self.source_color_mode == 'RGB565':
            # Framebuffer is 2 bytes per pixel (RGB565)
            row_bytes = width * 2
            
            if scale == 1:
                # No upscaling, convert to 3 bytes per pixel RGB666
                output_bytes = rw * 3
                lb = memoryview(self._linebuf[:output_bytes])
                for row in range(rh):
                    fb_byte_offset = (y + row) * row_bytes + x * 2
                    fb_word_offset = fb_byte_offset // 2
                    _rgb565_to_888_line(lb, src, fb_word_offset, rw)
                    self._spi.write(lb)
            else:
                # Upscaling with RGB666 conversion
                output_line_bytes = rw * scale * 3
                lb = memoryview(self._linebuf[:output_line_bytes])
                for row in range(rh):
                    fb_byte_offset = (y + row) * row_bytes + x * 2
                    fb_word_offset = fb_byte_offset // 2
                    _rgb565_to_888_upscale_line(lb, src, fb_word_offset, rw, scale)
                    # Write the line 'scale' times for vertical upscaling
                    for _ in range(scale):
                        self._spi.write(lb)
                        
        else: # RGB332
            # Framebuffer is 1 byte per pixel (RGB332)
            row_bytes = width

            if scale == 1:
                # No upscaling - convert RGB332 to RGB666
                output_bytes = rw * 3
                lb = memoryview(self._linebuf[:output_bytes]) if output_bytes < len(self._linebuf) else memoryview(self._linebuf)
                for row in range(rh):
                    fb_offset = (y + row) * row_bytes + x
                    _rgb332_to_888_line(lb, src, fb_offset, rw)
                    self._spi.write(lb)
            else:
                # Upscaling with RGB332 to RGB666 conversion
                output_line_bytes = rw * scale * 3
                lb = memoryview(self._linebuf[:output_line_bytes])
                for row in range(rh):
                    fb_offset = (y + row) * row_bytes + x
                    _rgb332_to_888_upscale_line(lb, src, fb_offset, rw, scale)
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
