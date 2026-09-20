from drawing import Drawing
import battery
from microcheck import check_pixels, summarize

WIDTH = 160
HEIGHT = 160

EXPECTED = {
    'battery right rgb565': 0x76108adb,
    'battery left rgb565': 0xe77d798e,
    'battery up rgb565': 0x5fc6d9ad,
    'battery down rgb565': 0xf5372ff7,
    'battery none rgb565': 0x1cc2745b,
    'battery gs8': 0xb51fb26a,
}

def scenario(label, color_mode, render):
    display = Drawing(WIDTH, HEIGHT, color_mode)
    render(display)
    check_pixels(label, display._framebuffer, EXPECTED.get(label))

def main():
    scenario('battery right rgb565', 'RGB565',
             lambda d: battery.draw_battery(d, (10, 10), (120, 60), 63))
    scenario('battery left rgb565', 'RGB565',
             lambda d: battery.draw_battery(d, (10, 10), (120, 60), 63, orientation='left'))
    scenario('battery up rgb565', 'RGB565',
             lambda d: battery.draw_battery(d, (10, 10), (60, 140), 30, orientation='up'))
    scenario('battery down rgb565', 'RGB565',
             lambda d: battery.draw_battery(d, (10, 10), (60, 140), 75, orientation='down'))
    scenario('battery none rgb565', 'RGB565',
             lambda d: battery.draw_battery(d, (10, 10), (120, 60), None))
    scenario('battery gs8', 'GS8',
             lambda d: battery.draw_battery(d, (10, 10), (120, 60), 63))

    summarize()

main()
