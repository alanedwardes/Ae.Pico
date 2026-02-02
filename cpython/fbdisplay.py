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
    def __init__(self, display_width, display_height, fb_width, fb_height, rotation=0, test_mode=False, fb_device='/dev/fb0'):
        self._display_width = display_width  # Physical framebuffer width
        self._display_height = display_height  # Physical framebuffer height
        self._fb_width = fb_width  # Drawing surface width
        self._fb_height = fb_height  # Drawing surface height
        self._rotation = rotation  # 0, 90, 180, 270
        self._test_mode = test_mode
        
        # Calculate logical (rotated) display dimensions
        if rotation in (90, 270):
            self._logical_width = display_height
            self._logical_height = display_width
        else:
            self._logical_width = display_width
            self._logical_height = display_height
        
        # Calculate scale factors (may differ for X and Y if aspect ratios don't match)
        self._scale_x = self._logical_width // fb_width
        self._scale_y = self._logical_height // fb_height
        
        print(f"FbDisplay: Physical {display_width}x{display_height}, Logical {self._logical_width}x{self._logical_height}")
        print(f"FbDisplay: Drawing {fb_width}x{fb_height}, Scale {self._scale_x}x{self._scale_y}, Rotation {rotation}°")
        
        # Open and memory-map the framebuffer
        self._fb_fd = os.open(fb_device, os.O_RDWR)
        fb_size = display_width * display_height * 2  # RGB565 = 2 bytes per pixel
        self._fb_mmap = mmap.mmap(self._fb_fd, fb_size, mmap.MAP_SHARED, mmap.PROT_WRITE | mmap.PROT_READ)
        
        # Working buffer (RGB565)
        self._buffer = bytearray(fb_size)
        self._buffer_view16 = memoryview(self._buffer).cast('H')
        
        # Clear to black
        for i in range(display_width * display_height):
            self._buffer_view16[i] = 0
        self._flush()

    def create(provider):
        config = provider['config']['display']

        # Physical display dimensions (what the framebuffer reports)
        display_width = config['width']
        display_height = config['height']
        
        # Drawing surface dimensions (what the app renders to)
        fb_width = config.get('fb_width', 320)
        fb_height = config.get('fb_height', 240)
        
        rotation = config.get('rotate', 0)  # degrees: 0/90/180/270
        test_mode = config.get('test_mode', False)
        fb_device = config.get('fb_device', '/dev/fb0')

        driver = FbDisplay(
            display_width, display_height,
            fb_width, fb_height,
            rotation=rotation, test_mode=test_mode,
            fb_device=fb_device
        )
        drawing = Drawing(fb_width, fb_height)
        drawing.set_driver(driver)

        provider['display'] = drawing
        return driver

    def _flush(self):
        """Write buffer to framebuffer."""
        self._fb_mmap.seek(0)
        self._fb_mmap.write(self._buffer)

    def _transform_coords(self, lx, ly):
        """Transform logical coordinates to physical framebuffer coordinates."""
        if self._rotation == 0:
            return lx, ly
        elif self._rotation == 90:
            # Rotate 90° clockwise
            return self._logical_height - 1 - ly, lx
        elif self._rotation == 180:
            return self._logical_width - 1 - lx, self._logical_height - 1 - ly
        elif self._rotation == 270:
            # Rotate 270° clockwise (90° counter-clockwise)
            return ly, self._logical_width - 1 - lx
        return lx, ly

    def _fill_rgb565(self, color565):
        """Fill entire buffer with an RGB565 color."""
        for i in range(self._display_width * self._display_height):
            self._buffer_view16[i] = color565

    def _rgb_to_565(self, r, g, b):
        """Convert 8-bit RGB to 16-bit RGB565."""
        return ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)

    async def start(self):
        if self._test_mode:
            print(f"FbDisplay: TEST MODE")
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
                print(f"FbDisplay: {name}")
                idx = (idx + 1) % len(colors)
                await asyncio.sleep(1)

        await asyncio.Event().wait()

    def set_backlight(self, brightness):
        pass

    def render(self, framebuffer, width, height, region):
        """Render RGB565 framebuffer region to display with scaling and rotation."""
        x, y, rw, rh = region
        if x < 0 or y < 0 or rw <= 0 or rh <= 0:
            return
        if x + rw > width or y + rh > height:
            return
        if width != self._fb_width or height != self._fb_height:
            return

        src16 = memoryview(framebuffer).cast('H')
        dest16 = self._buffer_view16
        scale_x = self._scale_x
        scale_y = self._scale_y

        for row in range(rh):
            fb_row = y + row
            for col in range(rw):
                fb_col = x + col
                src_idx = fb_row * width + fb_col
                pixel = src16[src_idx]
                
                # Write upscaled and rotated pixel block
                for dy in range(scale_y):
                    for dx in range(scale_x):
                        # Logical position (scaled)
                        lx = fb_col * scale_x + dx
                        ly = fb_row * scale_y + dy
                        
                        # Transform to physical position
                        px, py = self._transform_coords(lx, ly)
                        
                        # Write to physical buffer
                        if 0 <= px < self._display_width and 0 <= py < self._display_height:
                            dest_idx = py * self._display_width + px
                            dest16[dest_idx] = pixel

        self._flush()

    def __del__(self):
        if hasattr(self, '_fb_mmap') and self._fb_mmap:
            self._fb_mmap.close()
        if hasattr(self, '_fb_fd') and self._fb_fd:
            os.close(self._fb_fd)
