"""
Direct Linux framebuffer display driver.
No pygame dependency - uses only Python standard library.
Works on Raspberry Pi and other Linux systems with /dev/fb0.
"""
import asyncio
import sys
import os
import mmap
from array import array
from drawing import Drawing

class FbDisplay:
    def __init__(self, display_width, display_height, scale=1, debug_regions=False, test_mode=False, fb_device='/dev/fb0'):
        self._display_width = display_width
        self._display_height = display_height
        self._scale = scale
        self._debug_regions = debug_regions
        self._test_mode = test_mode
        
        # Open and memory-map the framebuffer
        self._fb_fd = os.open(fb_device, os.O_RDWR)
        fb_size = display_width * display_height * 4  # ARGB8888
        self._fb_mmap = mmap.mmap(self._fb_fd, fb_size, mmap.MAP_SHARED, mmap.PROT_WRITE | mmap.PROT_READ)
        print(f"FbDisplay: Opened {fb_device}: {display_width}x{display_height} ({fb_size} bytes)")
        
        # Working buffer (ARGB8888 format to match typical fb)
        self._buffer = bytearray(fb_size)
        self._buffer_view32 = memoryview(self._buffer).cast('I')
        
        # Precompute RGB565 -> ARGB8888 lookup table
        lut = array('I', [0]) * 65536
        for val in range(65536):
            r5 = (val >> 11) & 0x1F
            g6 = (val >> 5) & 0x3F
            b5 = val & 0x1F
            r = (r5 << 3) | (r5 >> 2)
            g = (g6 << 2) | (g6 >> 4)
            b = (b5 << 3) | (b5 >> 2)
            # ARGB8888 in little-endian memory: BGRA byte order
            lut[val] = (0xFF << 24) | (r << 16) | (g << 8) | b
        self._lut565 = lut
        
        # Clear to black
        self._buffer_view32[:] = array('I', [0xFF000000]) * (display_width * display_height)
        self._flush()

    def create(provider):
        config = provider['config']['display']

        display_width = config['width']
        display_height = config['height']
        scale = config.get('scale', 1)
        test_mode = config.get('test_mode', False)
        fb_device = config.get('fb_device', '/dev/fb0')

        fb_width = display_width // scale
        fb_height = display_height // scale

        driver = FbDisplay(
            display_width, display_height,
            scale=scale, debug_regions=False,
            test_mode=test_mode, fb_device=fb_device
        )
        drawing = Drawing(fb_width, fb_height)
        drawing.set_driver(driver)

        provider['display'] = drawing
        return driver

    def _flush(self):
        """Write buffer to framebuffer."""
        self._fb_mmap.seek(0)
        self._fb_mmap.write(self._buffer)

    def _fill(self, color):
        """Fill entire buffer with an ARGB color."""
        r, g, b = color
        argb = (0xFF << 24) | (r << 16) | (g << 8) | b
        self._buffer_view32[:] = array('I', [argb]) * (self._display_width * self._display_height)

    async def start(self):
        if self._test_mode:
            print(f"FbDisplay: TEST MODE - Resolution: {self._display_width}x{self._display_height}")
            colors = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 255)]
            idx = 0
            while True:
                c = colors[idx]
                self._fill(c)
                self._flush()
                print(f"FbDisplay: Color {c}")
                idx = (idx + 1) % len(colors)
                await asyncio.sleep(1)

        # Normal mode: just stay alive
        await asyncio.Event().wait()

    def set_backlight(self, brightness):
        pass

    def render(self, framebuffer, width, height, region):
        x, y, rw, rh = region
        if x < 0 or y < 0 or rw <= 0 or rh <= 0:
            return
        if x + rw > width or y + rh > height:
            return
        scale = self._scale
        if width * scale != self._display_width or height * scale != self._display_height:
            return

        src16 = memoryview(framebuffer).cast('H')
        dest32 = self._buffer_view32
        lut = self._lut565

        for row in range(rh):
            fb_row = y + row
            for col in range(rw):
                fb_col = x + col
                src_idx = fb_row * width + fb_col
                argb = lut[src16[src_idx]]
                for dy in range(scale):
                    for dx in range(scale):
                        dest_x = (x + col) * scale + dx
                        dest_y = (y + row) * scale + dy
                        dest_idx = dest_y * self._display_width + dest_x
                        dest32[dest_idx] = argb

        self._flush()

    def __del__(self):
        if hasattr(self, '_fb_mmap') and self._fb_mmap:
            self._fb_mmap.close()
        if hasattr(self, '_fb_fd') and self._fb_fd:
            os.close(self._fb_fd)
