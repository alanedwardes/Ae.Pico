import os
import pygame
import asyncio
import sys
import numpy as np
import signal
from drawing import Drawing

class PygameDisplay:
    def __init__(self, display_width, display_height, framebuffer, fb_width, fb_height, color_mode='RGB565', scale=1, flags=0, hide_mouse=False, push_fps=60):
        # Force exit on Ctrl+C
        signal.signal(signal.SIGINT, lambda sig, frame: os._exit(0))

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

        self._fb = framebuffer
        self._fb_width = fb_width
        self._fb_height = fb_height
        self._bpp = 2 if color_mode == 'RGB565' else 1
        self._frame_interval = 1.0 / push_fps if push_fps else 0

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

        # Precompute 8-bit RGB332 -> 32-bit RGBA8888 lookup table
        vals332 = np.arange(256, dtype=np.uint32)
        r3 = (vals332 >> 5) & 0x07
        g3 = (vals332 >> 2) & 0x07
        b2 = vals332 & 0x03

        r8 = (r3 * 255) // 7
        g8 = (g3 * 255) // 7
        b8 = (b2 * 255) // 3

        self._lut332_rgba = (255 << 24) | (b8 << 16) | (g8 << 8) | r8
        self._lut332_rgba = self._lut332_rgba.astype(np.uint32)

    def create(provider):
        config = provider['config']['display']

        # Get configurable dimensions and scale
        display_width = config['width']
        display_height = config['height']
        scale = config.get('scale', 1)
        flags = config.get('flags', 0)
        hide_mouse = config.get('hide_mouse', False)
        mode = config.get('mode', 'RGB565')
        push_fps = config.get('push_fps', 60)

        # Framebuffer dimensions are display dimensions divided by scale
        fb_width = display_width // scale
        fb_height = display_height // scale

        drawing = Drawing(fb_width, fb_height, color_mode=mode)
        driver = PygameDisplay(display_width, display_height, drawing.framebuffer, fb_width, fb_height, color_mode=mode, scale=scale, flags=flags, hide_mouse=hide_mouse, push_fps=push_fps)
        drawing.set_driver(driver)

        provider['display'] = drawing
        return driver

    async def start(self):
        try:
            while True:
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        print("Pygame QUIT received, exiting...")
                        pygame.quit()
                        os._exit(0)
                    elif event.type == pygame.VIDEORESIZE:
                        self._window_width = event.w
                        self._window_height = event.h
                        self.screen = pygame.display.set_mode((self._window_width, self._window_height), self._flags)
                self._push_frame()
                await asyncio.sleep(self._frame_interval)
        except asyncio.CancelledError:
            pass
        finally:
            print("PygameDisplay shutting down...")
            pygame.quit()

    def set_backlight(self, brightness):
        pass  # No backlight on pygame

    def _push_frame(self):
        fb = self._fb
        if fb is None:
            return

        width = self._fb_width
        height = self._fb_height
        scale = self._scale

        if self._bpp == 1:
            src = np.frombuffer(fb, dtype=np.uint8).reshape((height, width))
            rgba = self._lut332_rgba[src]
        else:
            src = np.frombuffer(fb, dtype=np.uint16).reshape((height, width))
            rgba = self._lut565_rgba[src]

        if scale > 1:
            rgba = rgba.repeat(scale, axis=0).repeat(scale, axis=1)

        self._rgba[:rgba.shape[0], :rgba.shape[1]] = rgba

        if self._window_width != self._display_width or self._window_height != self._display_height:
            scaled = pygame.transform.scale(self._surf, (self._window_width, self._window_height))
            self.screen.blit(scaled, (0, 0))
        else:
            self.screen.blit(self._surf, (0, 0))
        pygame.display.flip()