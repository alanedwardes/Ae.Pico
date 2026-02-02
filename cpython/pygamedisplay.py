import pygame
import asyncio
import sys
import random
import numpy as np
from drawing import Drawing

class PygameDisplay:
    def __init__(self, display_width, display_height, scale=1, debug_regions=False, flags=0, hide_mouse=False):
        pygame.init()
        driver_name = pygame.display.get_driver()
        print(f"Pygame initialized. Driver: {driver_name}")
        
        print(f"Display: Requesting {display_width}x{display_height} with flags {flags}")
        self._flags = flags | pygame.RESIZABLE
        self.screen = pygame.display.set_mode((display_width, display_height), self._flags)
        print(f"Display: Actual {self.screen.get_width()}x{self.screen.get_height()}")
        if hide_mouse:
            pygame.mouse.set_visible(False)
        self._display_width = display_width
        self._display_height = display_height
        self._window_width = display_width
        self._window_height = display_height
        self._scale = scale
        self._debug_regions = debug_regions

        # Persistent RGBA buffer as a numpy array (uint32)
        # We use a 2D array for easy slicing/indexing
        self._rgba = np.zeros((display_height, display_width), dtype=np.uint32)
        
        # Create pygame surface from the numpy array buffer
        self._surf = pygame.image.frombuffer(self._rgba, (display_width, display_height), 'RGBA')

        # Precompute 16-bit RGB565 -> 32-bit RGBA8888 lookup table using numpy
        vals = np.arange(65536, dtype=np.uint32)
        r5 = (vals >> 11) & 0x1F
        g6 = (vals >> 5) & 0x3F
        b5 = vals & 0x1F
        
        r = (r5 << 3) | (r5 >> 2)
        g = (g6 << 2) | (g6 >> 4)
        b = (b5 << 3) | (b5 >> 2)
        
        # little-endian RGBA bytes: A B G R -> (255 << 24) | (b << 16) | (g << 8) | r
        self._lut565_rgba = (255 << 24) | (b << 16) | (g << 8) | r
        self._lut565_rgba = self._lut565_rgba.astype(np.uint32)

    def create(provider):
        config = provider['config']['display']

        # Get configurable dimensions and scale
        display_width = config['width']
        display_height = config['height']
        scale = config.get('scale', 1)
        flags = config.get('flags', 0)
        hide_mouse = config.get('hide_mouse', False)


        # Framebuffer dimensions are display dimensions divided by scale
        fb_width = display_width // scale
        fb_height = display_height // scale

        driver = PygameDisplay(display_width, display_height, scale=scale, debug_regions=False, flags=flags, hide_mouse=hide_mouse)
        drawing = Drawing(fb_width, fb_height)
        drawing.set_driver(driver)

        provider['display'] = drawing
        return driver
              
    async def start(self):
        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    sys.exit()
                elif event.type == pygame.VIDEORESIZE:
                    self._window_width = event.w
                    self._window_height = event.h
                    self.screen = pygame.display.set_mode((self._window_width, self._window_height), self._flags)
            await asyncio.sleep(0.1)

    def set_backlight(self, brightness):
        pass  # No backlight on pygame

    def render(self, framebuffer, width, height, region):
        # Unpack and validate region (region is in framebuffer coordinates)
        x, y, rw, rh = region
        if x < 0 or y < 0 or rw <= 0 or rh <= 0:
            return
        if x + rw > width or y + rh > height:
            return
        
        scale = self._scale
        # Check scaled dimensions match display size
        if width * scale != self._display_width or height * scale != self._display_height:
            return

        # View framebuffer as 2D numpy array of uint16
        # Note: We assume framebuffer is a bytearray/memoryview that is contiguous
        src_fb = np.frombuffer(framebuffer, dtype=np.uint16).reshape((height, width))
        
        # Extract Region of Interest
        # Slicing creates a view in numpy, so this is efficient
        src_roi = src_fb[y:y+rh, x:x+rw]
        
        # Convert to RGBA using LUT
        # This allocates a new array for the region
        rgba_roi = self._lut565_rgba[src_roi]
        
        # Upscale if necessary
        if scale > 1:
            # repeat elements: similar to kron or repeat
            # axis 0 is rows, axis 1 is cols
            rgba_upscaled = rgba_roi.repeat(scale, axis=0).repeat(scale, axis=1)
        else:
            rgba_upscaled = rgba_roi

        # Write to the persistent display buffer
        # Since self._rgba is a 2D array, we can assign to the slice directly
        dest_x = x * scale
        dest_y = y * scale
        dest_h, dest_w = rgba_upscaled.shape
        
        self._rgba[dest_y:dest_y+dest_h, dest_x:dest_x+dest_w] = rgba_upscaled

        # Draw debug rectangle into display buffer (at display resolution)
        if self._debug_regions:
            # Generate random color and convert to RGBA
            r = random.randint(0, 255)
            g = random.randint(0, 255)
            b = random.randint(0, 255)
            # Make opaque RGBA
            debug_rgba = (255 << 24) | (b << 16) | (g << 8) | r
            
            # Scaled region bounds
            sx, sy = x * scale, y * scale
            srw, srh = rw * scale, rh * scale

            # Draw borders using numpy slicing
            
            # Top edge
            if sy < self._display_height:
                row_slice = self._rgba[sy:min(sy+2, self._display_height), sx:min(sx+srw, self._display_width)]
                row_slice[:] = debug_rgba

            # Bottom edge
            bottom_y = sy + srh - 1
            if bottom_y >= 0 and bottom_y < self._display_height:
                 # Ensure we don't go out of bounds with the thickness
                 start_y = max(bottom_y - 1, 0)
                 row_slice = self._rgba[start_y:bottom_y+1, sx:min(sx+srw, self._display_width)]
                 row_slice[:] = debug_rgba

            # Left edge
            if sx < self._display_width:
                 col_slice = self._rgba[sy:min(sy+srh, self._display_height), sx:min(sx+2, self._display_width)]
                 col_slice[:] = debug_rgba

            # Right edge
            right_x = sx + srw - 1
            if right_x >= 0 and right_x < self._display_width:
                 start_x = max(right_x - 1, 0)
                 col_slice = self._rgba[sy:min(sy+srh, self._display_height), start_x:right_x+1]
                 col_slice[:] = debug_rgba

        if self._window_width != self._display_width or self._window_height != self._display_height:
             scaled = pygame.transform.scale(self._surf, (self._window_width, self._window_height))
             self.screen.blit(scaled, (0, 0))
        else:
             self.screen.blit(self._surf, (0, 0))
        pygame.display.flip()
