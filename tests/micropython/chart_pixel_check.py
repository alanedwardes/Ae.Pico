import asyncio

from drawing import Drawing
import chart
from microcheck import check, check_pixels, summarize

WIDTH = 320
HEIGHT = 120

VALUES = [0.0, 0.1, 0.45, 0.3, 0.8, 1.0, 0.65, 0.2, 0.5, 0.9, 0.35, 0.0]
RAW = [v * 10 for v in VALUES]
Q8 = [int(v * 256) for v in VALUES]

EXPECTED = {
    'segmented area rgb565': 0xea79d576,
    'segmented area linear': 0xa9b93240,
    'colored points rgb565': 0xc0c03aaf,
    'segmented area gs8': 0xdf2485ed,
}

def color_fn(index, value):
    if value > 7:
        return 0xFF3B30
    if value > 4:
        return 0xFFCC00
    return 0x34C759

def scenario(label, color_mode, render):
    display = Drawing(WIDTH, HEIGHT, color_mode)
    asyncio.run(render(display))
    check_pixels(label, display._framebuffer, EXPECTED.get(label))

def check_kernel_matches_reference():
    y_origin, width, height = 10, 300, 100
    n = len(VALUES)
    nseg = n - 1
    norm = [q / 256 for q in Q8]
    padded = [norm[0]] + norm + [norm[-1]]
    for smoothing in (1.0, 0.5, 0.0):
        cols = chart._compute_curve(y_origin, width, height, Q8, int(smoothing * 256))
        worst = 0
        for c in range(width + 1):
            scaled = c * nseg
            i = min(scaled // width, nseg - 1)
            t = (scaled - i * width) / width
            y0, y1, y2, y3 = ((1 - padded[i + k]) * height for k in range(4))
            py = chart.lerp(chart.lerp(y1, y2, t),
                            chart.catmull_rom(y0, y1, y2, y3, t),
                            smoothing) + y_origin
            ref = int(py * 256)
            if ref < 0:
                ref = 0
            dy = abs(cols[c] - ref)
            if dy > worst:
                worst = dy
        check('kernel vs float ref smoothing=%.1f' % smoothing, worst <= 256,
              'max |dy| = %d/256 px' % worst)

def main():
    check_kernel_matches_reference()
    scenario('segmented area rgb565', 'RGB565',
             lambda d: chart.draw_segmented_area(d, 10, 10, 300, 100, RAW, Q8, color_fn))
    scenario('segmented area linear', 'RGB565',
             lambda d: chart.draw_segmented_area(d, 10, 10, 300, 100, RAW, Q8, color_fn, smoothing=0.0))
    scenario('colored points rgb565', 'RGB565',
             lambda d: chart.draw_colored_points(d, 10, 10, 300, 100, RAW, Q8, color_fn, radius=2))
    scenario('segmented area gs8', 'GS8',
             lambda d: chart.draw_segmented_area(d, 10, 10, 300, 100, RAW, Q8, color_fn))

    summarize()

main()