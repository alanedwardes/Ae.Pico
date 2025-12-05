import pygame
import sys

class NeoPixel:
    def __init__(self, pin, n, *, bpp=3, timing=1):
        pygame.init()
        self.n = n
        self._buffer = [(0, 0, 0)] * n

        # Simulation display properties
        self.led_size = 5
        self.padding = 1
        self.leds_per_row = 60
        
        num_rows = (n + self.leds_per_row - 1) // self.leds_per_row
        width = self.leds_per_row * (self.led_size + self.padding)
        height = num_rows * (self.led_size + self.padding)

        self.screen = pygame.display.set_mode((width, height))
        pygame.display.set_caption("WLED NeoPixel Simulator")

    def __setitem__(self, index, val):
        if index < self.n:
            self._buffer[index] = val

    def write(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

        self.screen.fill((0, 0, 0)) # Black background

        for i, color in enumerate(self._buffer):
            row = i // self.leds_per_row
            col = i % self.leds_per_row
            x = col * (self.led_size + self.padding)
            y = row * (self.led_size + self.padding)
            r, g, b = [max(0, min(255, int(c))) for c in color]
            pygame.draw.rect(self.screen, (r, g, b), (x, y, self.led_size, self.led_size))
        
        pygame.display.flip()
