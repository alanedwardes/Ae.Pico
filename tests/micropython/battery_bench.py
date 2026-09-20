from drawing import Drawing
import battery
from microbench import bench

def main():
    display = Drawing(320, 240, 'RGB565')

    bench('draw_battery right (120x60)',
          lambda: battery.draw_battery(display, (10, 10), (120, 60), 63))
    bench('draw_battery up (60x140)',
          lambda: battery.draw_battery(display, (10, 10), (60, 140), 30, orientation='up'))
    bench('draw_battery none (120x60)',
          lambda: battery.draw_battery(display, (10, 10), (120, 60), None))

main()
