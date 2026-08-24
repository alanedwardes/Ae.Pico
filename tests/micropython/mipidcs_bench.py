import machine
from st7789 import ST7789, LANDSCAPE
from drawing import Drawing
from microbench import bench

FB_WIDTH = 320
FB_HEIGHT = 240

def main():
    spi = machine.SPI()
    dc = machine.Pin(1)
    cs = machine.Pin(2)
    bl = machine.Pin(3)
    st = ST7789(spi, cs=cs, dc=dc, backlight=bl, height=FB_HEIGHT, width=FB_WIDTH,
                disp_mode=LANDSCAPE, display=(0, 0, 1, 0, True), scale=1,
                source_color_mode='RGB565')

    drawing = Drawing(FB_WIDTH, FB_HEIGHT, 'RGB565')
    drawing.set_driver(st)
    drawing.fill(0x336699)

    bench('render full frame (320x240)',
          lambda: drawing.update())

    bench('render dirty region (100x20, e.g. a clock digit)',
          lambda: drawing.update((10, 10, 100, 20)))

    bench('render single row (320x1)',
          lambda: drawing.update((0, 0, FB_WIDTH, 1)))

main()