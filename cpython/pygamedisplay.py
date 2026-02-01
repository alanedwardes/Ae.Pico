import pygame
import asyncio
import sys
import random
from array import array
from drawing import Drawing

class PygameDisplay:
    def __init__(self, display_width, display_height, scale=1, debug_regions=False, flags=0, hide_mouse=False, test_mode=False):
        pygame.init()
        driver_name = pygame.display.get_driver()
        print(f"Pygame initialized. Driver: {driver_name}")
        
        print(f"Display: Requesting {display_width}x{display_height} with flags {flags}")
        self.screen = pygame.display.set_mode((display_width, display_height), flags)
        print(f"Display: Actual {self.screen.get_width()}x{self.screen.get_height()}")
        if hide_mouse:
            pygame.mouse.set_visible(False)
        self._display_width = display_width
        self._display_height = display_height
        self._scale = scale
        self._debug_regions = debug_regions
        self._test_mode = test_mode
        # Persistent RGBA buffer and surface at display resolution (avoid per-frame allocations)
        self._rgba = bytearray(display_width * display_height * 4)
        self._rgba_view32 = memoryview(self._rgba).cast('I')
        self._surf = pygame.image.frombuffer(self._rgba, (display_width, display_height), 'RGBA')
        # Precompute 16-bit RGB565 -> 32-bit RGBA8888 lookup table
        lut = array('I', [0]) * 65536
        for val in range(65536):
            r5 = (val >> 11) & 0x1F
            g6 = (val >> 5) & 0x3F
            b5 = val & 0x1F
            r = (r5 << 3) | (r5 >> 2)
            g = (g6 << 2) | (g6 >> 4)
            b = (b5 << 3) | (b5 >> 2)
            lut[val] = (255 << 24) | (b << 16) | (g << 8) | r  # little-endian RGBA bytes
        self._lut565_rgba = lut

    def create(provider):
        config = provider['config']['display']

        # Get configurable dimensions and scale
        display_width = config['width']
        display_height = config['height']
        scale = config.get('scale', 1)
        flags = config.get('flags', 0)
        hide_mouse = config.get('hide_mouse', False)
        test_mode = config.get('test_mode', False)

        # Framebuffer dimensions are display dimensions divided by scale
        fb_width = display_width // scale
        fb_height = display_height // scale

        driver = PygameDisplay(display_width, display_height, scale=scale, debug_regions=False, flags=flags, hide_mouse=hide_mouse, test_mode=test_mode)
        drawing = Drawing(fb_width, fb_height)
        drawing.set_driver(driver)

        provider['display'] = drawing
        return driver
              
    async def start(self):
        if self._test_mode:
            info = pygame.display.Info()
            print(f"PygameDisplay: TEST MODE ENABLED - Driver: {pygame.display.get_driver()}")
            print(f"PygameDisplay: Resolution: {info.current_w}x{info.current_h}")
            
            s = self.screen
            print(f"Surface Details: size={s.get_size()}, depth={s.get_bitsize()}, flags=0x{s.get_flags():x}")
            print(f"Surface Masks: {s.get_masks()}")
            
            print("PygameDisplay: Cycling colors")
            colors = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 255)]
            idx = 0
            while True:
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        sys.exit()
                
                c = colors[idx]
                self.screen.fill(c)
                pygame.display.flip()
                print(f"PygameDisplay: Test Color {c}")
                
                idx = (idx + 1) % len(colors)
                await asyncio.sleep(1)

        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    sys.exit()
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
        # Check scaled dimensions match display size
        scale = self._scale
        if width * scale != self._display_width or height * scale != self._display_height:
            return

        # Convert region pixels from RGB565 to RGBA with upscaling
        src16 = memoryview(framebuffer).cast('H')  # native-endian uint16
        dest32 = self._rgba_view32
        lut = self._lut565_rgba

        for row in range(rh):
            fb_row = y + row
            for col in range(rw):
                fb_col = x + col
                src_idx = fb_row * width + fb_col
                rgba = lut[src16[src_idx]]
                # Write upscaled pixel block
                for dy in range(scale):
                    for dx in range(scale):
                        dest_x = (x + col) * scale + dx
                        dest_y = (y + row) * scale + dy
                        dest_idx = dest_y * self._display_width + dest_x
                        dest32[dest_idx] = rgba

        # Draw debug rectangle into display buffer (at display resolution)
        if self._debug_regions:
            # Generate random color and convert to RGBA via LUT
            r = random.randint(0, 255)
            g = random.randint(0, 255)
            b = random.randint(0, 255)
            debug_color_565 = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
            debug_rgba = lut[debug_color_565]

            # Scaled region bounds
            sx, sy = x * scale, y * scale
            srw, srh = rw * scale, rh * scale

            # Top and bottom edges
            for col in range(sx, min(sx + srw, self._display_width)):
                for border_row in range(2):
                    # Top edge
                    if sy + border_row < self._display_height:
                        idx = (sy + border_row) * self._display_width + col
                        dest32[idx] = debug_rgba
                    # Bottom edge
                    if sy + srh - 1 - border_row >= 0 and sy + srh - 1 - border_row < self._display_height:
                        idx = (sy + srh - 1 - border_row) * self._display_width + col
                        dest32[idx] = debug_rgba
            # Left and right edges
            for row in range(sy, min(sy + srh, self._display_height)):
                for border_col in range(2):
                    # Left edge
                    if sx + border_col < self._display_width:
                        idx = row * self._display_width + (sx + border_col)
                        dest32[idx] = debug_rgba
                    # Right edge
                    if sx + srw - 1 - border_col >= 0 and sx + srw - 1 - border_col < self._display_width:
                        idx = row * self._display_width + (sx + srw - 1 - border_col)
                        dest32[idx] = debug_rgba

        self.screen.blit(self._surf, (0, 0))
        pygame.display.flip()
