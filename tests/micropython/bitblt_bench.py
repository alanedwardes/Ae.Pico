import struct
from io import BytesIO

from bitblt import blit_region
from microbench import bench

FB_WIDTH = 320
FB_HEIGHT = 480
ICON_W = 24
ICON_H = 24

class FB:
    def __init__(self, width, height, bytes_per_pixel):
        self.width = width
        self.height = height
        self.bytes_per_pixel = bytes_per_pixel
        self._buf = bytearray(width * height * bytes_per_pixel)

def main():
    icon = BytesIO(struct.pack('<HH', ICON_W, ICON_H) + bytes(ICON_W * ICON_H))
    fb565 = FB(FB_WIDTH, FB_HEIGHT, 2)
    icon_buf = memoryview(bytearray(ICON_W))

    bench('blit_region gs8 icon, with buffer',
          lambda: blit_region(fb565, FB_WIDTH, FB_HEIGHT, 2, icon, 4, ICON_W,
                              0, 0, ICON_W, ICON_H, 50, 50, buffer=icon_buf, src_format=6))

    bench('blit_region gs8 icon, NO buffer (fallback alloc path)',
          lambda: blit_region(fb565, FB_WIDTH, FB_HEIGHT, 2, icon, 4, ICON_W,
                              0, 0, ICON_W, ICON_H, 50, 50, src_format=6))

    bench('blit_region gs8 icon, clipped (half off-screen)',
          lambda: blit_region(fb565, FB_WIDTH, FB_HEIGHT, 2, icon, 4, ICON_W,
                              0, 0, ICON_W, ICON_H, FB_WIDTH - ICON_W // 2, 50,
                              buffer=icon_buf, src_format=6, clip=(0, 0, FB_WIDTH, FB_HEIGHT)))

main()