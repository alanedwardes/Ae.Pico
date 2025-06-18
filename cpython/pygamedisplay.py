import pygame
import asyncio
import sys
import HersheyFonts
import pygamefont8

class PygameDisplay:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((320, 240))
        self.pen = None
        self.font = None
        self.thickness = 1

        self.serif = HersheyFonts.HersheyFonts()
        self.serif.load_default_font()

    def create(provider):
        display = PygameDisplay()
        provider['display'] = display
        return display
              
    async def start(self):
        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    sys.exit()
            await asyncio.sleep(0.1)

    def update(self):
        pygame.display.flip()

    def create_pen(self, r, g, b):
        return (r, g, b)

    def set_font(self, font):
        self.font = font

    def set_pen(self, pen):
        self.pen = pen

    def rectangle(self, x, y, width, height):
        pygame.draw.rect(self.screen, self.pen, (x, y, width, height))

    def circle(self, x, y, radius):
        pygame.draw.circle(self.screen, self.pen, (x, y), radius)

    def polygon(self, points):
        pygame.draw.polygon(self.screen, self.pen, points)

    def pixel(self, x, y):
        self.rectangle(x, y, 1, 1)

    def set_thickness(self, thickness):
        self.thickness = thickness

    def get_bounds(self):
        return (self.screen.get_width(), self.screen.get_height())
    
    def __get_font(self, scale):
        name, size = self.fonts[self.font]
        return pygame.font.SysFont(name, int(size * scale))
    
    def __get_serif_lines(self, text, scale):
        return [((x1 * scale, y1 * scale), (x2 * scale, y2 * scale)) for (x1, y1), (x2, y2) in self.serif.lines_for_text(text)]

    def measure_text(self, text, scale = 1, spacing = 1, fixed_width = False):
        if self.font == 'bitmap8':
            return pygamefont8.Font8.measure_text(text, scale, spacing)
        elif self.font == 'sans':
            lines = self.__get_serif_lines(text, scale)
            width = max([x2 for (x1, y1), (x2, y2) in lines])
            return width
        else:
            raise NotImplementedError(f"Font '{self.font}' not supported for measure_text")

    def text(self, text, x, y, scale = 1):
        if self.font == 'bitmap8':
            pygamefont8.Font8.draw_text(self.screen, text, x, y, self.pen, 1, scale)
        elif self.font == 'sans':
            for (x1, y1), (x2, y2) in self.__get_serif_lines(text, scale):
                pygame.draw.line(self.screen, self.pen, (x + x1, y + y1), (x + x2, y + y2), self.thickness)
        else:
            raise NotImplementedError(f"Font '{self.font}' not supported for text")
