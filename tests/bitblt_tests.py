import sys
import unittest
import io
import os
# Add project root, infodisplay and cpython to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../infodisplay')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../cpython')))

try:
    import framebuf
except ImportError:
    # If not in path, try direct import from cpython
    from cpython import framebuf

from bitblt import blit_region

class TestBitBlt(unittest.TestCase):
    def setUp(self):
        self.width = 100
        self.height = 100
        self.fb_data = bytearray(self.width * self.height * 2) # RGB565
        self.fb = framebuf.FrameBuffer(self.fb_data, self.width, self.height, framebuf.RGB565)
        # Mocking bytes_per_pixel on the fb object since it's expected by bitblt
        self.fb.bytes_per_pixel = 2

    def test_clipping_basic(self):
        # Create a source: 10x10 GS8, all white (0xFF)
        src_data = bytearray([0xFF] * 100)
        fh = io.BytesIO(b'\x00\x00\x00\x00' + src_data) # 4-byte header
        
        # Blit partly off-screen (left/top)
        blit_region(self.fb, self.width, self.height, 1, fh, 4, 10,
                    0, 0, 10, 10, -5, -5)
        
        # Only (5,5) to (9,9) of source should be blitted to (0,0) to (4,4) of dest
        # We'll check dest[0,0]
        
        val = (self.fb_data[1] << 8) | self.fb_data[0]
        self.assertEqual(val, 0xFFFF)

    def test_clipping_right_bottom(self):
        src_data = bytearray([0xFF] * 100)
        fh = io.BytesIO(b'\x00\x00\x00\x00' + src_data)
        
        # Blit partly off-screen (right/bottom)
        blit_region(self.fb, self.width, self.height, 1, fh, 4, 10,
                    0, 0, 10, 10, 95, 95)
        
        # Check dest[99,99]
        idx = (99 * self.width + 99) * 2
        val = (self.fb_data[idx+1] << 8) | self.fb_data[idx]
        self.assertEqual(val, 0xFFFF)

    def test_rgb565_blit(self):
        # Source: 2x2 RGB565 (Blue: 0x001F)
        src_data = bytearray([0x1F, 0x00, 0x1F, 0x00, 0x1F, 0x00, 0x1F, 0x00])
        fh = io.BytesIO(src_data) # no header
        
        blit_region(self.fb, self.width, self.height, 2, fh, 0, 4,
                    0, 0, 2, 2, 0, 0)
        
        val = (self.fb_data[1] << 8) | self.fb_data[0]
        self.assertEqual(val, 0x001F)

    def test_gs8_with_palette(self):
        # Palette: maps 0x01 to Red (0xF800)
        palette = bytearray([0x00] * 512)
        palette[2] = 0x00; palette[3] = 0xF8 # Little-endian 0xF800 is [0x00, 0xF8]
        
        src_data = bytearray([0x01] * 4) # 2x2
        fh = io.BytesIO(src_data)
        
        blit_region(self.fb, self.width, self.height, 1, fh, 0, 2,
                    0, 0, 2, 2, 0, 0, palette=palette)
        
        val = (self.fb_data[1] << 8) | self.fb_data[0]
        self.assertEqual(val, 0xF800)

    def test_8bit_to_8bit_blit(self):
        # Create 8-bit dest
        fb8_data = bytearray(self.width * self.height)
        fb8 = framebuf.FrameBuffer(fb8_data, self.width, self.height, framebuf.GS8)
        fb8.bytes_per_pixel = 1
        
        # Source: 2x2 8-bit (Value 0x42)
        src_data = bytearray([0x42] * 4)
        fh = io.BytesIO(src_data)
        
        blit_region(fb8, self.width, self.height, 1, fh, 0, 2,
                    0, 0, 2, 2, 0, 0)
        
        self.assertEqual(fb8_data[0], 0x42)

    def test_gs8_to_8bit_palette_blit(self):
        # Create 8-bit dest
        fb8_data = bytearray(self.width * self.height)
        fb8 = framebuf.FrameBuffer(fb8_data, self.width, self.height, framebuf.GS8)
        fb8.bytes_per_pixel = 1
        
        # 8-bit palette: map 0x01 -> 0xE0 (Red in RGB332)
        palette = bytearray([0x00] * 256)
        palette[1] = 0xE0
        
        src_data = bytearray([0x01] * 4)
        fh = io.BytesIO(src_data)
        
        blit_region(fb8, self.width, self.height, 1, fh, 0, 2,
                    0, 0, 2, 2, 0, 0, palette=palette)
        
        self.assertEqual(fb8_data[0], 0xE0)

    def test_transparency_gs8_to_rgb565_palette(self):
        palette = bytearray([0x00] * 512)
        # map 0x01 to 0xF800, keep 0x00 as whatever (it's transparency key)
        palette[2] = 0x00; palette[3] = 0xF8
        
        # fill fb with blue
        for i in range(0, len(self.fb_data), 2):
            self.fb_data[i] = 0x1F
            self.fb_data[i+1] = 0x00
            
        src_data = bytearray([0x00, 0x01, 0x00, 0x01]) # 2x2
        fh = io.BytesIO(src_data)
        
        blit_region(self.fb, self.width, self.height, 1, fh, 0, 2,
                    0, 0, 2, 2, 0, 0, palette=palette, key=0)
                    
        val0 = (self.fb_data[1] << 8) | self.fb_data[0]
        val1 = (self.fb_data[3] << 8) | self.fb_data[2]
        
        self.assertEqual(val0, 0x001F) # Should remain blue (transparent)
        self.assertEqual(val1, 0xF800) # Should be red

    def test_transparency_rgb565(self):
        # fill fb with blue
        for i in range(0, len(self.fb_data), 2):
            self.fb_data[i] = 0x1F
            self.fb_data[i+1] = 0x00
            
        src_data = bytearray([0x00, 0x00, 0x00, 0xF8, 0x00, 0x00, 0x00, 0xF8]) # 2x2, key is 0x0000
        fh = io.BytesIO(src_data)
        
        blit_region(self.fb, self.width, self.height, 2, fh, 0, 4,
                    0, 0, 2, 2, 0, 0, src_format=1, key=0)
                    
        val0 = (self.fb_data[1] << 8) | self.fb_data[0]
        val1 = (self.fb_data[3] << 8) | self.fb_data[2]
        
        self.assertEqual(val0, 0x001F) # Should remain blue
        self.assertEqual(val1, 0xF800) # Should be red

    def test_transparency_8bit_to_8bit(self):
        fb8_data = bytearray(self.width * self.height)
        fb8 = framebuf.FrameBuffer(fb8_data, self.width, self.height, framebuf.GS8)
        fb8.bytes_per_pixel = 1
        
        for i in range(len(fb8_data)):
            fb8_data[i] = 0xAA
            
        src_data = bytearray([0x00, 0xFF, 0x00, 0xFF]) # key is 0
        fh = io.BytesIO(src_data)
        
        blit_region(fb8, self.width, self.height, 1, fh, 0, 2,
                    0, 0, 2, 2, 0, 0, key=0)
                    
        self.assertEqual(fb8_data[0], 0xAA)
        self.assertEqual(fb8_data[1], 0xFF)

if __name__ == '__main__':
    unittest.main()
