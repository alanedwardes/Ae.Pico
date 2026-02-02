"""
Direct Linux framebuffer display driver (RGB565).
No pygame dependency - uses only Python standard library + numpy.
Works on Raspberry Pi and other Linux systems with /dev/fb0.
"""
import asyncio
import os
import mmap
import numpy as np
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
        
        # Calculate uniform scale factor (letterbox - fit without stretching)
        scale_x = self._logical_width // fb_width
        scale_y = self._logical_height // fb_height
        self._scale = min(scale_x, scale_y)  # Uniform scale
        
        # Calculate centering offset
        scaled_width = fb_width * self._scale
        scaled_height = fb_height * self._scale
        self._offset_x = (self._logical_width - scaled_width) // 2
        self._offset_y = (self._logical_height - scaled_height) // 2
        
        print(f"FbDisplay: Physical {display_width}x{display_height}, Logical {self._logical_width}x{self._logical_height}")
        print(f"FbDisplay: Drawing {fb_width}x{fb_height}, Scale {self._scale}x, Offset ({self._offset_x}, {self._offset_y})")
        
        # Open and memory-map the framebuffer
        self._fb_fd = os.open(fb_device, os.O_RDWR)
        fb_size = display_width * display_height * 2  # RGB565 = 2 bytes per pixel
        self._fb_mmap = mmap.mmap(self._fb_fd, fb_size, mmap.MAP_SHARED, mmap.PROT_WRITE | mmap.PROT_READ)
        
        # Create numpy array view of mmap for fast writes
        self._fb_array = np.ndarray((display_height, display_width), dtype=np.uint16, 
                                     buffer=self._fb_mmap)
        
        # Clear to black
        self._fb_array.fill(0)

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
                self._fb_array.fill(color565)
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

        # Convert source framebuffer to numpy array (height x width)
        src = np.frombuffer(framebuffer, dtype=np.uint16).reshape((height, width))
        
        # Extract the region to update
        region_data = src[y:y+rh, x:x+rw]
        
        # Scale using numpy repeat (uniform scale)
        scale = self._scale
        if scale > 1:
            scaled = np.repeat(np.repeat(region_data, scale, axis=0), scale, axis=1)
        else:
            scaled = region_data
        
        # Apply rotation
        if self._rotation == 90:
            rotated = np.rot90(scaled, k=-1)  # 90° clockwise = k=-1
        elif self._rotation == 180:
            rotated = np.rot90(scaled, k=2)
        elif self._rotation == 270:
            rotated = np.rot90(scaled, k=1)  # 270° clockwise = 90° counter-clockwise
        else:
            rotated = scaled
        
        # Calculate destination position with centering offset
        scaled_x = x * scale + self._offset_x
        scaled_y = y * scale + self._offset_y
        
        if self._rotation == 0:
            dest_x, dest_y = scaled_x, scaled_y
        elif self._rotation == 90:
            # After 90° CW rotation, top-left of scaled region goes to:
            dest_x = self._logical_height - scaled_y - scaled.shape[0]
            dest_y = scaled_x
        elif self._rotation == 180:
            dest_x = self._logical_width - scaled_x - scaled.shape[1]
            dest_y = self._logical_height - scaled_y - scaled.shape[0]
        elif self._rotation == 270:
            dest_x = scaled_y
            dest_y = self._logical_width - scaled_x - scaled.shape[1]
        else:
            dest_x, dest_y = scaled_x, scaled_y
        
        # Clip to framebuffer bounds
        rh_out, rw_out = rotated.shape
        if dest_x < 0:
            rotated = rotated[:, -dest_x:]
            rw_out = rotated.shape[1]
            dest_x = 0
        if dest_y < 0:
            rotated = rotated[-dest_y:, :]
            rh_out = rotated.shape[0]
            dest_y = 0
        if dest_x + rw_out > self._display_width:
            rw_out = self._display_width - dest_x
            rotated = rotated[:, :rw_out]
        if dest_y + rh_out > self._display_height:
            rh_out = self._display_height - dest_y
            rotated = rotated[:rh_out, :]
        
        # Write directly to mmap via numpy view (very fast!)
        if rh_out > 0 and rw_out > 0:
            self._fb_array[dest_y:dest_y+rh_out, dest_x:dest_x+rw_out] = rotated

    def __del__(self):
        if hasattr(self, '_fb_mmap') and self._fb_mmap:
            self._fb_mmap.close()
        if hasattr(self, '_fb_fd') and self._fb_fd:
            os.close(self._fb_fd)
