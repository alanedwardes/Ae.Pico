from drawing import Drawing
import gauge
from microcheck import check_pixels, summarize

WIDTH = 160
HEIGHT = 160

EXPECTED = {
    'gauge min/max rgb565': 0xc94fd0fc,
    'gauge thermostat rgb565': 0xa7017137,
    'gauge no range': 0xcd467f42,
    'gauge gs8': 0xa3f06365,
}

def scenario(label, color_mode, render):
    display = Drawing(WIDTH, HEIGHT, color_mode)
    render(display)
    check_pixels(label, display._framebuffer, EXPECTED.get(label))

def main():
    scenario('gauge min/max rgb565', 'RGB565',
             lambda d: gauge.draw_gauge(d, (10, 10), (140, 140), 15.0, 25.0, 21.5))
    scenario('gauge thermostat rgb565', 'RGB565',
             lambda d: gauge.draw_gauge(d, (10, 10), (140, 140), 15.0, 25.0, 20.0, 21.5, False,
                                        groove_color=0x424142, notch_outline_color=0x848284))
    scenario('gauge no range', 'RGB565',
             lambda d: gauge.draw_gauge(d, (10, 10), (140, 140)))
    scenario('gauge gs8', 'GS8',
             lambda d: gauge.draw_gauge(d, (10, 10), (140, 140), 15.0, 25.0, 21.5))

    summarize()

main()