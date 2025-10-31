import pygame
import asyncio
import sys
from drawing import Drawing

class PygameDisplay:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((320, 240), pygame.HWSURFACE | pygame.DOUBLEBUF, depth=32)
        self._width = 320
        self._height = 240

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
        mv = memoryview(framebuffer)
        num_pixels = width * height
        rgba = bytearray(num_pixels * 4)
        j = 0
        for i in range(0, num_pixels * 2, 2):
            val = mv[i] | (mv[i + 1] << 8)
            r5 = (val >> 11) & 0x1F
            g6 = (val >> 5) & 0x3F
            b5 = val & 0x1F
            r = (r5 << 3) | (r5 >> 2)
            g = (g6 << 2) | (g6 >> 4)
            b = (b5 << 3) | (b5 >> 2)
            rgba[j] = r
            rgba[j + 1] = g
            rgba[j + 2] = b
            rgba[j + 3] = 255
            j += 4
        surf = pygame.image.frombuffer(rgba, (width, height), 'RGBA')
        self.screen.blit(surf, (0, 0))
        pygame.display.flip()
