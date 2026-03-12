import sys
import os
import struct

# Mock micropython
import builtins
builtins.ptr8 = object
builtins.ptr16 = object
builtins.ptr32 = object

class MockMicropython:
    @staticmethod
    def viper(func):
        return func
sys.modules['micropython'] = MockMicropython()

# Mock framebuf for CPython
class MockFrameBuffer:
    def __init__(self, buffer, width, height, format):
        pass
    def blit(self, fbuf, x, y, key=-1, palette=None):
        pass

class MockFramebufModule:
    FrameBuffer = MockFrameBuffer
    RGB565 = 1
    GS8 = 6
sys.modules['framebuf'] = MockFramebufModule()

# Ensure we can import modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'infodisplay')))

from bmfont import BMFont, draw_text
from bitblt import blit_region
import framebuf

# Constants
FONT_PATH = 'cpython/fonts/regular.fnt'
ICON_PATH = 'cpython/icons/weather_0.bin'
FB_WIDTH = 320
FB_HEIGHT = 480

class MockFB(bytearray):
    def __init__(self, width, height, bpp):
        super().__init__(width * height * bpp)
        self.width = width
        self.height = height
        self.bytes_per_pixel = bpp
        self.fb = framebuf.FrameBuffer(self, width, height, framebuf.RGB565 if bpp==2 else framebuf.GS8)
    
    def blit(self, *args, **kwargs):
        return self.fb.blit(*args, **kwargs)

def create_gray_palette():
    pal = bytearray(256 * 2)
    for i in range(256):
        r = (i * 31) // 255
        g = (i * 63) // 255
        b = (i * 31) // 255
        val = (r << 11) | (g << 5) | b
        struct.pack_into('<H', pal, i * 2, val)
    return pal

GRAY_PALETTE = create_gray_palette()

# --- Pytest Benchmarks ---

def test_benchmark_icon(benchmark):
    fb = MockFB(FB_WIDTH, FB_HEIGHT, 2)
    
    def run_icon():
        with open(ICON_PATH, 'rb') as f:
            w, h = struct.unpack('<HH', f.read(4))
            blit_region(fb, FB_WIDTH, FB_HEIGHT, 2, f, 4, w, 0, 0, w, h, 50, 50, src_format=6, palette=GRAY_PALETTE)
            
    benchmark(run_icon)


def test_benchmark_font(benchmark):
    fb = MockFB(FB_WIDTH, FB_HEIGHT, 2)
    font = BMFont.load(FONT_PATH)
    text = "The quick brown fox jumps over the lazy dog!"
    linebuf = bytearray(font.scale_w * 2)
    
    def run_font():
        with open('cpython/fonts/regular_0.bin', 'rb') as fh:
            draw_text(fb, FB_WIDTH, FB_HEIGHT, font, {0: fh}, text, 10, 10, linebuf=linebuf)
            
    benchmark(run_font)
