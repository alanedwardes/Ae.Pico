import pygame
import asyncio
import sys
from array import array
from drawing import Drawing

class PygameDisplay:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((320, 240), pygame.HWSURFACE | pygame.DOUBLEBUF, depth=32)
        self._width = 320
        self._height = 240
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
        driver = PygameDisplay()
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

    def render(self, framebuffer, width, height):
        # framebuffer: memoryview/bytes of little-endian RGB565
        if width != self._width or height != self._height:
            self._width, self._height = width, height
            self._rgba = bytearray(self._width * self._height * 4)
            self._rgba_view32 = memoryview(self._rgba).cast('I')
            self._surf = pygame.image.frombuffer(self._rgba, (self._width, self._height), 'RGBA')

        num_pixels = width * height
        src16 = memoryview(framebuffer).cast('H')  # native-endian uint16
        dest32 = self._rgba_view32
        lut = self._lut565_rgba

        # Fast per-pixel table lookup (assign 32-bit RGBA words)
        for i in range(num_pixels):
            dest32[i] = lut[src16[i]]

        self.screen.blit(self._surf, (0, 0))
        pygame.display.flip()
