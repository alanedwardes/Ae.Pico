from time import sleep_ms
import gc
import micropython
import rp2
from machine import PWM, Pin
import os

# User orientation constants
LANDSCAPE = 0  # Default
REFLECT = 1
USD = 2
PORTRAIT = 4
# Display types
GENERIC = 0x000000

# SPI Hardware Register offsets (common to RP2040/RP2350)
_SPI_SSPDR_OFFSET = 0x08
_SPI_SSPDMACR_OFFSET = 0x24
_SPI_TXDMAE_BIT = 0x02

# Detect chip type for hardware addresses and DREQs
_machine = os.uname().machine
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
    # Fallback/Unknown - DMA paths will be disabled in __init__
    _SPI0_BASE = 0
    _SPI1_BASE = 0
    _DREQ_SPI0_TX = 0
    _DREQ_SPI1_TX = 0

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
    # Convert r, g, b in range 0-255 to a 16-bit RGB565 colour value
    @staticmethod
    def rgb(r, g, b):
        return ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)

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
                 scale=1,
                 source_color_mode='RGB565'):
        self._offset = display[:2]
        orientation = display[2]
        self._spi_init = False # Standard
        
        self._spi = spi
        self._cs = cs
        self._dc = dc
        self._rst = rst
        self._backlight = backlight
        self._backlight_pwm = None
        self.width = width
        self.height = height
        self._current_mode = disp_mode
        self._display = display
        self._scale = scale
        self.source_color_mode = source_color_mode
        self._linebuf = bytearray(self.width * 3)
        
        self._dma = None
        self._dma_active = False
        
        # Internal DMA logic (auto-enable on RP2 hardware)
        use_dma = True
        if _SPI0_BASE == 0: # Unknown chip detected in module-level code
            use_dma = False
        else:
            try:
                import rp2
            except ImportError:
                use_dma = False
                    
        if use_dma:
            self._setup_dma()

        self._init(disp_mode, orientation, display[3:])
        self._backlight_pwm = None

    def _setup_dma(self):
        # Identify SPI bus and base address
        spi_str = str(self._spi)
        if "SPI(0," in spi_str:
            base = _SPI0_BASE
            dreq = _DREQ_SPI0_TX
        elif "SPI(1," in spi_str:
            base = _SPI1_BASE
            dreq = _DREQ_SPI1_TX
        else:
            print("DMA: Could not identify SPI bus from", spi_str)
            return

        if base == 0:
            print("DMA: Hardware addresses not mapped for this chip.")
            return

        self._spi_dr = base + _SPI_SSPDR_OFFSET
        self._spi_dmacr = base + _SPI_SSPDMACR_OFFSET
        
        # Enable DMA on SPI hardware
        # We use a viper-like write to the SPI register
        @micropython.viper
        def _enable_spi_dma(addr: int, bit: int):
            p = ptr32(addr)
            p[0] |= bit
        
        _enable_spi_dma(self._spi_dmacr, _SPI_TXDMAE_BIT)
        
        # Claim DMA channel
        import rp2
        self._dma = rp2.DMA()
        self._dma_ctrl = self._dma.pack_ctrl(
            size=0, # 8-bit transfers
            inc_read=True,
            inc_write=False,
            treq_sel=dreq
        )
        
        # We need two line buffers for ping-pong
        self._linebuf_pair = [bytearray(self.width * 3), bytearray(self.width * 3)]
        self._linebuf_idx = 0

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

    def render(self, fb, width, height, bbox):
        """Write a framebuffer region to the display."""
        x, y, rw, rh = bbox
        if x < 0 or y < 0 or rw <= 0 or rh <= 0:
            return
        if x + rw > width or y + rh > height:
            return
            
        scale = self._scale
        
        # Set hardware window to scaled region
        self._set_region_window(x, y, rw, rh)

        # Send RAMWR command (0x2C)
        self._wcmd(b"\x2c")
        
        self._dc(1)
        self._cs(0)
        
        if self._dma:
            # High-performance DMA Path
            src = fb
            dr = self._spi_dr
            ctrl = self._dma_ctrl
            
            if self.source_color_mode == 'RGB565':
                line_conv = _rgb565_to_888_line if scale == 1 else _rgb565_to_888_upscale_line
            else:
                line_conv = _rgb332_to_888_line if scale == 1 else _rgb332_to_888_upscale_line
            
            for row in range(rh):
                # Pick next buffer in ping-pong
                buf = self._linebuf_pair[self._linebuf_idx]
                self._linebuf_idx = (self._linebuf_idx + 1) & 1
                
                # Convert this row while the previous DMA (if any) is running
                if scale == 1:
                    line_conv(buf, src, (y + row) * width + x, rw)
                else:
                    line_conv(buf, src, (y + row) * width + x, rw, scale)
                
                # Each source row handles 'scale' vertical display rows
                for _ in range(scale):
                    # Wait for DMA to be ready (it might still be sending the PREVIOUS line or PREVIOUS scale-repeat)
                    while self._dma.active():
                        pass
                    
                    self._dma.config(
                        read=buf,
                        write=dr,
                        count=rw * scale * 3,
                        ctrl=ctrl,
                        trigger=True
                    )
            
            # Final wait for completion
            while self._dma.active():
                pass
        else:
            # Standard Path
            linebuf = self._linebuf
            if self.source_color_mode == 'RGB565':
                line_conv = _rgb565_to_888_line if scale == 1 else _rgb565_to_888_upscale_line
            else:
                line_conv = _rgb332_to_888_line if scale == 1 else _rgb332_to_888_upscale_line

            for row in range(rh):
                if scale == 1:
                    line_conv(linebuf, fb, (y + row) * width + x, rw)
                else:
                    line_conv(linebuf, fb, (y + row) * width + x, rw, scale)
                
                for _ in range(scale):
                    self._spi.write(linebuf[:rw * scale * 3])
                    
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
