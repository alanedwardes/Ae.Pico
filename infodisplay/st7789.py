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
def _swapline(dest: ptr8, source: ptr8, length: int):
    n: int = 0
    while length:
        b0 = source[n]
        b1 = source[n + 1]
        dest[n] = b1
        dest[n + 1] = b0
        n += 2
        length -= 2

@micropython.viper
def _upscale_line(dest: ptr8, source: ptr8, src_pixels: int, scale: int):
    """Upscale a line by duplicating each pixel 'scale' times horizontally, with byte swap."""
    s: int = 0  # source byte index
    d: int = 0  # dest byte index
    while src_pixels:
        # Read source pixel (2 bytes), swap for SPI
        b0 = source[s]
        b1 = source[s + 1]
        # Write duplicated pixels (swapped byte order)
        for _ in range(scale):
            dest[d] = b1
            dest[d + 1] = b0
            d += 2
        s += 2
        src_pixels -= 1

@micropython.viper
def _blit_line_palette(dest: ptr8, source: ptr8, count: int, palette: ptr8):
    """Blit a GS8 line to RGB565 using a palette, with byte swapping for SPI."""
    d: int = 0
    s: int = 0
    while count:
        idx: int = int(source[s])
        # Palette is 256 * 2 bytes. Each entry is RGB565.
        
        # In bmfont.py: val = (tr5 << 11) | (tg6 << 5) | tb5. Then pal[o] = val & 0xFF, pal[o+1] = (val >> 8)
        # So palette is Little Endian bytes.
        # We want to write Upper, then Lower for SPI.
        
        p_offset: int = idx << 1
        lo: int = palette[p_offset]
        hi: int = palette[p_offset + 1]
        
        # Write Hi then Lo
        dest[d] = hi
        dest[d + 1] = lo
        
        d += 2
        s += 1
        count -= 1

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

        # Prepare buffers
        src = memoryview(framebuffer)
        row_bytes = width * 2  # Full framebuffer row width

        if scale == 1:
            # No upscaling - original behavior
            region_bytes = rw * 2
            lb = memoryview(self._linebuf[:region_bytes]) if region_bytes < len(self._linebuf) else memoryview(self._linebuf)
            for row in range(rh):
                fb_offset = (y + row) * row_bytes + x * 2
                _swapline(lb, src[fb_offset:], region_bytes)
                self._spi.write(lb)
        else:
            # Upscaling: duplicate each pixel scale times horizontally and vertically
            output_line_bytes = rw * scale * 2
            lb = memoryview(self._linebuf[:output_line_bytes])
            for row in range(rh):
                fb_offset = (y + row) * row_bytes + x * 2
                _upscale_line(lb, src[fb_offset:], rw, scale)
                # Write the line 'scale' times for vertical upscaling
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

    def fill_rect(self, x, y, w, h, color):
        """Draw a filled rectangle directly to the display."""
        # Clip to screen dimensions
        if x < 0:
            w += x
            x = 0
        if y < 0:
            h += y
            y = 0
        if x + w > self.width:
            w = self.width - x
        if y + h > self.height:
            h = self.height - y
            
        if w <= 0 or h <= 0:
            return

        self._set_region_window(x, y, w, h)
        
        # Convert color to bytes (swapped for SPI)
        # color is usually RGB565 integer
        hi = (color >> 8) & 0xFF
        lo = color & 0xFF
        
        bytes_per_line = w * 2
        if bytes_per_line > len(self._linebuf):
             chunk_size = len(self._linebuf) // 2
        else:
             chunk_size = w
             
        # optimize: fill line buffer once
        lb = memoryview(self._linebuf)[:chunk_size*2]
        for i in range(0, chunk_size * 2, 2):
            self._linebuf[i] = hi
            self._linebuf[i+1] = lo
            
        self._dc(0)
        self._cs(0)
        self._spi.write(b"\x2c") # RAMWR
        self._dc(1)
        
        pixels_remaining = w * h
        pixels_in_chunk = chunk_size
        
        while pixels_remaining > 0:
            to_write = pixels_in_chunk if pixels_remaining >= pixels_in_chunk else pixels_remaining
            # If to_write is less than full chunk, we just write the slice
            if to_write == pixels_in_chunk:
                self._spi.write(lb)
            else:
                self._spi.write(lb[:to_write*2])
            pixels_remaining -= to_write
            
        self._cs(1)

    def fill(self, color):
        """Fill the entire screen with a color."""
        self.fill_rect(0, 0, self.width, self.height, color)

    def pixel(self, x, y, color):
        """Draw a single pixel."""
        if x < 0 or x >= self.width or y < 0 or y >= self.height:
            return
            
        self._set_region_window(x, y, 1, 1)
        
        self._dc(0)
        self._cs(0)
        self._spi.write(b"\x2c")
        self._dc(1)
        
        # Write color bytes (swapped)
        self._spi.write(bytes([(color >> 8) & 0xFF, color & 0xFF]))
        
        self._cs(1)

    def line(self, x0, y0, x1, y1, color):
        """Draw a line using Bresenham's algorithm."""
        dx = abs(x1 - x0)
        dy = abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx - dy

        while True:
            self.pixel(x0, y0, color)
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                x0 += sx
            if e2 < dx:
                err += dx
                y0 += sy

    def hline(self, x, y, w, color):
        """Draw a horizontal line."""
        self.fill_rect(x, y, w, 1, color)

    def vline(self, x, y, h, color):
        """Draw a vertical line."""
        self.fill_rect(x, y, 1, h, color)

    def ellipse(self, x, y, xr, yr, color, fill=False, m=15):
        """Draw an ellipse."""
        # Bresenham-like ellipse algorithm
        # Based on standard midpoint ellipse algorithm
        # m is bitmask: 1=TR, 2=TL, 4=BL, 8=BR (MicroPython standard)
        
        def draw_quads(cx, cy, dx, dy):
             if fill:
                 # Fill logic: vlines or hlines
                 # For ellipse fill, we usually draw hlines between left and right boundaries
                 # But we also need to respect the mask 'm'. 
                 # If we have full mask 15, we draw full hlines.
                 # If partial mask, it's weird for fill. 
                 # framebuf documentation says: "The optional f parameter, set to True to fill the ellipse"
                 # It doesn't explicitly talk about mask with fill. 
                 # Usually mask is for drawing corners of rounded rects.
                 # Let's support outline first effectively. 
                 pass
                 
        # Simplified implementation for outline (fill not implemented fully yet unless requested complexity is high)
        # If fill is True, we proceed to fill.
        
        # We'll use a standard implementation that supports quadrants
        # Note: This runs on the Pico, interpreted Python might be slow for pixel-by-pixel.
        # But this is what we have.
        
        two_asquare = 2 * xr * xr
        two_bsquare = 2 * yr * yr
        x_pos = xr
        y_pos = 0
        change_x = yr * yr * (1 - 2 * xr)
        change_y = xr * xr
        ellipse_error = 0
        stopping_x = two_bsquare * xr
        stopping_y = 0
        
        while stopping_x >= stopping_y:
            self._ellipse_points(x, y, x_pos, y_pos, color, fill, m)
            y_pos += 1
            stopping_y += two_asquare
            ellipse_error += change_y
            change_y += two_asquare
            if ((2 * ellipse_error) + change_x) > 0:
                x_pos -= 1
                stopping_x -= two_bsquare
                ellipse_error += change_x
                change_x += two_bsquare

        x_pos = 0
        y_pos = yr
        change_x = yr * yr
        change_y = xr * xr * (1 - 2 * yr)
        ellipse_error = 0
        stopping_x = 0
        stopping_y = two_asquare * yr
        
        while stopping_x <= stopping_y:
             self._ellipse_points(x, y, x_pos, y_pos, color, fill, m)
             x_pos += 1
             stopping_x += two_bsquare
             ellipse_error += change_x
             change_x += two_bsquare
             if ((2 * ellipse_error) + change_y) > 0:
                 y_pos -= 1
                 stopping_y -= two_asquare
                 ellipse_error += change_y
                 change_y += two_asquare

    def _ellipse_points(self, cx, cy, x, y, color, fill, m):
        if fill:
            # Fill usually draws lines. 
            # For each y step, we draw horizontal line from -x to +x (if both sides enabled)
            # This is called multiple times per scanline in the loop, which is inefficient (overdraw).
            # But correct enough.
            
            # Quadrants: 1=TR (x>0, y>0 in local), 2=TL (x<0, y>0), 4=BL (x<0, y<0), 8=BR (x>0, y<0)
            # Note: local y is usually down-positive in screen coords. 
            # In algebra y is up-positive. 
            # Let's adhere to screen coords: +y is down. 
            # TR: +x, -y (relative to center)? No, in screen +x is right, +y is down.
            # So TR is top-right. Top is -y. Right is +x. 
            # Mask 1 (TR) -> (+x, -y)
            # Mask 2 (TL) -> (-x, -y)
            # Mask 4 (BL) -> (-x, +y)
            # Mask 8 (BR) -> (+x, +y)
            
            # Wait, MicroPython `m` usage:
            # 1: TR (top-right)
            # 2: TL (top-left)
            # 4: BL (bottom-left)
            # 8: BR (bottom-right)
            
            # If fill, we draw hlines.
            # If TR and TL are both set, we draw hline from -x to +x at -y.
            if (m & 1) and (m & 2):
                 self.hline(cx - x, cy - y, 2 * x + 1, color)
            elif (m & 1):
                 self.hline(cx, cy - y, x + 1, color)
            elif (m & 2):
                 self.hline(cx - x, cy - y, x + 1, color)
                 
            # If BR and BL are both set, hline from -x to +x at +y
            if (m & 4) and (m & 8):
                 self.hline(cx - x, cy + y, 2 * x + 1, color)
            elif (m & 8):
                 self.hline(cx, cy + y, x + 1, color)
            elif (m & 4):
                 self.hline(cx - x, cy + y, x + 1, color)
        else:
            # Outline pixels
            if (m & 8): self.pixel(cx + x, cy + y, color) # BR (+x, +y)
            if (m & 4): self.pixel(cx - x, cy + y, color) # BL (-x, +y)
            if (m & 2): self.pixel(cx - x, cy - y, color) # TL (-x, -y)
            if (m & 1): self.pixel(cx + x, cy - y, color) # TR (+x, -y)

    def poly(self, x, y, coords, color, fill=False):
        """Draw a polygon. Fill not supported efficiently, ignores fill=True."""
        # coords is array of x,y,x,y...
        if len(coords) < 4:
            return
            
        # Draw lines connecting points
        for i in range(0, len(coords) - 2, 2):
            x1 = coords[i] + x
            y1 = coords[i+1] + y
            x2 = coords[i+2] + x
            y2 = coords[i+3] + y
            self.line(x1, y1, x2, y2, color)
            
        # Close the loop
        if len(coords) >= 4:
             x1 = coords[-2] + x
             y1 = coords[-1] + y
             x2 = coords[0] + x
             y2 = coords[1] + y
             self.line(x1, y1, x2, y2, color)

    def rect(self, x, y, w, h, color, fill=False):
        """Draw a rectangle."""
        if fill:
            self.fill_rect(x, y, w, h, color)
        else:
            self.fill_rect(x, y, w, 1, color)            # Top
            self.fill_rect(x, y + h - 1, w, 1, color)    # Bottom
            self.fill_rect(x, y, 1, h, color)            # Left
            self.fill_rect(x + w - 1, y, 1, h, color)    # Right

    def blit(self, source, x, y, key=0, palette=None):
        """Blit to display. Compatible with framebuf.blit but direct to hardware.
        
        Args:
            source: Tuple (buffer, width, height, format) as used by bmfont/framebuf
            x, y: Destination coordinates
            key: Transparency key (ignored for now)
            palette: Framebuf palette as tuple (bytes, len, type, format) - required for GS8
        """
        # Unpack source tuple
        try:
            source_buf, w, h, fmt = source
        except (TypeError, ValueError):
            return 

        # Simple clipping (assuming bmfont handles most prior)
        if x < 0:
            # We don't support partial source rendering easily here without stride math
            # But bmfont.blit_region usually passes valid rects?
            # If x < 0, we should probably clip. 
            pass
        
        if x + w > self.width:
            w = self.width - x
        if y + h > self.height:
            h = self.height - y
        
        if w <= 0 or h <= 0:
            return

        # Prepare display window
        self._set_region_window(x, y, w, h)

        self._dc(0)
        self._cs(0)
        self._spi.write(b"\x2c")
        self._dc(1)

        # Handle GS8 with palette (bmfont case)
        if palette:
            # palette tuple: (palette_bytes, size, 1, type)
            pal_bytes = palette[0]
            
            src_mv = memoryview(source_buf)
            
            lb = self._linebuf
            stride = source[1] # original width
            
            dest_ptr = ptr8(lb)
            pal_ptr = ptr8(pal_bytes)
            
            for row in range(h):
                # Source is linear chunk for this batch
                start_idx = row * w
                src_slice = src_mv[start_idx : start_idx + w]
                src_ptr = ptr8(src_slice)
                
                # Convert line using Viper
                _blit_line_palette(dest_ptr, src_ptr, w, pal_ptr)
                
                # Write line
                self._spi.write(lb[:w*2])
        else:
            # RGB565 source (buffer, width, height, format)
            # We assume the source buffer is already in appropriate format (e.g. bytearray)
            # but usually it's RGB565 (native LE?), and we need BE for SPI.
            # _swapline does exactly this (LE RAM -> BE SPI).
            
            src_mv = memoryview(source_buf)
            lb = self._linebuf
            
            stride = source[1] * 2 # 2 bytes per pixel
            dest_ptr = ptr8(lb)
            
            for row in range(h):
                start_idx = row * stride
                # Ensure we have enough data (clipping might have happened above but source not sliced?)
                # We assume source buffer matches width/height passed in source tuple
                # If w < source[1], we need to stride correctly.
                # Actually, standard framebuf behavior for blit: the source IS the sprite.
                # But we might be blitting a sub-region OF a sprite?
                # Using framebuf.blit(src, x, y) usually takes the whole src.
                # If src was larger, `w` and `h` here come from `source` geometry (unpacked at top).
                # So we are blitting the whole source.
                
                src_slice = src_mv[start_idx : start_idx + w*2]
                src_ptr = ptr8(src_slice)
                
                # Check buffer size
                if len(lb) < w*2:
                     # This shouldn't happen if w <= self.width.
                     continue
                     
                _swapline(dest_ptr, src_ptr, w*2)
                self._spi.write(lb[:w*2])

        self._cs(1)
        
    async def load_stream(self, reader, x, y, w, h):
        """Load an RGB565 stream directly to display region."""
        if w <= 0 or h <= 0:
            return
            
        self._set_region_window(x, y, w, h)
        
        self._dc(0)
        self._cs(0)
        self._spi.write(b"\x2c")
        self._dc(1)
        
        # We need a buffer for reading chunks. 
        # _linebuf is self.width * 2. 
        # If w > self.width (shouldn't happen), we'd be in trouble.
        # But we can chunk any amount.
        
        # Read a row at a time to be safe and allow swapping?
        # Or read larger chunks if w is small?
        # Simpler: read row by row, swap, write. 
        
        row_bytes = w * 2
        # Use a temporary buffer for reading so we can swap into _linebuf
        # Note: _swapline(dest, src, ...)
        
        # If we read directly into _linebuf, we'd need to swap in-place? 
        # _swapline isn't in-place.
        # So we need a second buffer. 
        # We can allocate one row buffer.
        
        read_buf = bytearray(row_bytes)
        lb = self._linebuf
        dest_ptr = ptr8(lb)
        src_ptr = ptr8(read_buf)

        # We need to perform this loop h times
        # But wait, reader.readinto might not return full amount? 
        # It's a stream. We should ensure we read exactly row_bytes.
        
        for _ in range(h):
             # Read exactly row_bytes
             view = memoryview(read_buf)
             remaining = row_bytes
             while remaining > 0:
                 try:
                     # Attempt to await readinto (MicroPython)
                     # If reader is standard file, it might not be awaitable?
                     # But we are designing for async stream readers here.
                     n = await reader.readinto(view[row_bytes-remaining:])
                 except (AttributeError, TypeError):
                     # Fallback for sync readers (internal files?)
                     # Or if readinto is not async (standard file objects in MP are sync?)
                     # If we use `open('file.bin', 'rb')`, readinto is sync.
                     # But `remotedisplay` passes async stream.
                     # We should support both if possible? 
                     # Or just assume async for this method as it's named load_stream (implying streaming).
                     # Let's keep it simple: assume async stream for now as that's the use case.
                     # But if we want to fix it properly:
                     if hasattr(reader, 'readinto'):
                         n = reader.readinto(view[row_bytes-remaining:])
                     else:
                          raise
                          
                 if not n:
                     break # EOF handling?
                 remaining -= n
            
             _swapline(dest_ptr, src_ptr, row_bytes)
             self._spi.write(lb[:row_bytes])
             
        self._cs(1)

    def text(self, s, x, y, color=0xFFFF):
        # No built-in font support in ST7789 driver
        # Use textbox/bmfont for text rendering.
        pass
