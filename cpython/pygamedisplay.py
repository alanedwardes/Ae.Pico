import pygame
import asyncio
import sys
import random
from array import array
from drawing import Drawing

class PygameDisplay:
    def __init__(self, debug_regions=False):
        pygame.init()
        self.screen = pygame.display.set_mode((320, 240), pygame.HWSURFACE | pygame.DOUBLEBUF, depth=32)
        self._width = 320
        self._height = 240
        self._debug_regions = debug_regions
        # Persistent RGBA buffer and surface (avoid per-frame allocations)
        self._rgba = bytearray(self._width * self._height * 4)
        self._rgba_view32 = memoryview(self._rgba).cast('I')
        self._surf = pygame.image.frombuffer(self._rgba, (self._width, self._height), 'RGBA')
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
        driver = PygameDisplay(debug_regions=False)
        drawing = Drawing(driver._width, driver._height)
        drawing.set_driver(driver)
        provider['display'] = drawing
        return driver
              
    async def start(self):
        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    sys.exit()
            await asyncio.sleep(0.1)

    def render(self, framebuffer, width, height, region):
        # Unpack and validate region
        x, y, rw, rh = region
        if x < 0 or y < 0 or rw <= 0 or rh <= 0:
            return
        if x + rw > width or y + rh > height:
            return

        # Handle window resize
        if width != self._width or height != self._height:
            self._width, self._height = width, height
            self._rgba = bytearray(self._width * self._height * 4)
            self._rgba_view32 = memoryview(self._rgba).cast('I')
            self._surf = pygame.image.frombuffer(self._rgba, (self._width, self._height), 'RGBA')

        # Convert only region pixels from RGB565 to RGBA
        src16 = memoryview(framebuffer).cast('H')  # native-endian uint16
        dest32 = self._rgba_view32
        lut = self._lut565_rgba

        for row in range(rh):
            fb_row = y + row
            for col in range(rw):
                fb_col = x + col
                idx = fb_row * width + fb_col
                dest32[idx] = lut[src16[idx]]

        # Draw debug rectangle into framebuffer (persistent)
        if self._debug_regions:
            # Generate random color and convert to RGB565
            r = random.randint(0, 255)
            g = random.randint(0, 255)
            b = random.randint(0, 255)
            debug_color = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)

            # Top and bottom edges
            for col in range(x, min(x + rw, width)):
                for border_row in range(2):
                    # Top edge
                    if y + border_row < height:
                        idx = (y + border_row) * width + col
                        if idx < len(src16):
                            src16[idx] = debug_color
                            dest32[idx] = lut[debug_color]
                    # Bottom edge
                    if y + rh - 1 - border_row >= 0 and y + rh - 1 - border_row < height:
                        idx = (y + rh - 1 - border_row) * width + col
                        if idx < len(src16):
                            src16[idx] = debug_color
                            dest32[idx] = lut[debug_color]
            # Left and right edges
            for row in range(y, min(y + rh, height)):
                for border_col in range(2):
                    # Left edge
                    if x + border_col < width:
                        idx = row * width + (x + border_col)
                        if idx < len(src16):
                            src16[idx] = debug_color
                            dest32[idx] = lut[debug_color]
                    # Right edge
                    if x + rw - 1 - border_col >= 0 and x + rw - 1 - border_col < width:
                        idx = row * width + (x + rw - 1 - border_col)
                        if idx < len(src16):
                            src16[idx] = debug_color
                            dest32[idx] = lut[debug_color]

        self.screen.blit(self._surf, (0, 0))
        pygame.display.flip()
