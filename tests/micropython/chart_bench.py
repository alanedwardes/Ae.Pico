from drawing import Drawing
import chart
import gauge
from microbench import bench

WIDTH = 320
HEIGHT = 120

VALUES = [0.0, 0.1, 0.45, 0.3, 0.8, 1.0, 0.65, 0.2, 0.5, 0.9, 0.35, 0.0]
RAW = [v * 10 for v in VALUES]
VALUES_Q8 = [int(v * 256) for v in VALUES]

def color_fn(index, value):
    if value > 7:
        return 0xFF3B30
    if value > 4:
        return 0xFFCC00
    return 0x34C759

def main():
    display = Drawing(WIDTH, HEIGHT, 'RGB565')
    gauge_display = Drawing(160, 160, 'RGB565')

    def drain_chart():
        for _ in chart.draw_chart(10, 10, 300, 100, VALUES):
            pass

    bench('draw_chart drain (300px, float ref)', drain_chart)
    bench('compute curve (300px, viper)',
          lambda: chart._compute_curve(10, 300, 100, VALUES_Q8, 256))
    bench('segmented area (300px)',
          lambda: chart.draw_segmented_area(display, 10, 10, 300, 100, RAW, VALUES_Q8, color_fn))
    bench('colored points (300px)',
          lambda: chart.draw_colored_points(display, 10, 10, 300, 100, RAW, VALUES_Q8, color_fn, radius=2))
    bench('draw_gauge min/max',
          lambda: gauge.draw_gauge(gauge_display, (10, 10), (140, 140), 15.0, 25.0, 21.5))
    bench('draw_gauge thermostat',
          lambda: gauge.draw_gauge(gauge_display, (10, 10), (140, 140), 15.0, 25.0, 20.0, 21.5, False))

main()