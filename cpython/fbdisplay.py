"""
Direct Linux framebuffer display driver (RGB565).
No pygame dependency - uses only Python standard library.
Works on Raspberry Pi and other Linux systems with /dev/fb0.
"""
import asyncio
import os
import mmap
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
        fb_size = display_width * display_height * 2  # RGB565 = 2 bytes per pixel
        self._fb_mmap = mmap.mmap(self._fb_fd, fb_size, mmap.MAP_SHARED, mmap.PROT_WRITE | mmap.PROT_READ)
        print(f"FbDisplay: Opened {fb_device}: {display_width}x{display_height} RGB565 ({fb_size} bytes)")
        
        # Working buffer (RGB565)
        self._buffer = bytearray(fb_size)
        self._buffer_view16 = memoryview(self._buffer).cast('H')
        
        # Clear to black
        for i in range(display_width * display_height):
            self._buffer_view16[i] = 0
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

    def _fill_rgb565(self, color565):
        """Fill entire buffer with an RGB565 color."""
        for i in range(self._display_width * self._display_height):
            self._buffer_view16[i] = color565

    def _rgb_to_565(self, r, g, b):
        """Convert 8-bit RGB to 16-bit RGB565."""
        return ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)

    async def start(self):
        if self._test_mode:
            print(f"FbDisplay: TEST MODE - Resolution: {self._display_width}x{self._display_height}")
            # RGB565 colors
            colors = [
                (self._rgb_to_565(255, 0, 0), "Red"),
                (self._rgb_to_565(0, 255, 0), "Green"),
                (self._rgb_to_565(0, 0, 255), "Blue"),
                (self._rgb_to_565(255, 255, 255), "White"),
            ]
            idx = 0
            while True:
                color565, name = colors[idx]
                self._fill_rgb565(color565)
                self._flush()
                print(f"FbDisplay: {name} (0x{color565:04x})")
                idx = (idx + 1) % len(colors)
                await asyncio.sleep(1)

        await asyncio.Event().wait()

    def set_backlight(self, brightness):
        pass

    def render(self, framebuffer, width, height, region):
        """Render RGB565 framebuffer region to display with scaling."""
        x, y, rw, rh = region
        if x < 0 or y < 0 or rw <= 0 or rh <= 0:
            return
        if x + rw > width or y + rh > height:
            return
        scale = self._scale
        if width * scale != self._display_width or height * scale != self._display_height:
            return

        # Source is already RGB565 - just copy with upscaling
        src16 = memoryview(framebuffer).cast('H')
        dest16 = self._buffer_view16

        for row in range(rh):
            fb_row = y + row
            for col in range(rw):
                fb_col = x + col
                src_idx = fb_row * width + fb_col
                pixel = src16[src_idx]
                for dy in range(scale):
                    for dx in range(scale):
                        dest_x = (x + col) * scale + dx
                        dest_y = (y + row) * scale + dy
                        dest_idx = dest_y * self._display_width + dest_x
                        dest16[dest_idx] = pixel

        self._flush()

    def __del__(self):
        if hasattr(self, '_fb_mmap') and self._fb_mmap:
            self._fb_mmap.close()
        if hasattr(self, '_fb_fd') and self._fb_fd:
            os.close(self._fb_fd)
