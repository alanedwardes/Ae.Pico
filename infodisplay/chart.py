import asyncio
import sys
from array import array

try:
    import micropython
    IS_MICROPYTHON = sys.implementation.name == 'micropython'
except ImportError:
    IS_MICROPYTHON = False

if not IS_MICROPYTHON:
    # CPython mocking logic for simulator
    class micropython:
        @staticmethod
        def viper(f): return f

    ptr32 = object

def catmull_rom(p0, p1, p2, p3, t):
    return (
        0.5
        * (
            2 * p1
            + (-p0 + p2) * t
            + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t
            + (-p0 + 3 * p1 - 3 * p2 + p3) * t * t * t
        )
    )

def lerp(a, b, t):
    return a + (b - a) * t

def draw_chart(x, y, width, height, points, step=1, smoothing=1.0):
    """Float reference implementation of the curve.

    Yields one (px, py) per pixel column. This is the readable spec for
    what _curve_cols_viper computes -- the drawing functions below use
    the fixed-point kernel instead, because on MicroPython every float
    operation here allocates a boxed float on the heap (~1.5 KB per
    pixel column, hundreds of KB per redraw).
    """
    def get_point(idx):
        if idx < 0:
            return points[0]
        elif idx >= len(points):
            return points[-1]
        else:
            return points[idx]

    if len(points) < 2:
        return

    column_width = width / (len(points) - 1)

    for i in range(len(points) - 1):
        x0 = x + i * column_width
        x1 = x + (i + 1) * column_width

        j = 0
        while True:
            px = x0 + step * j
            if px >= x1:
                break
            t = (px - x0) / (x1 - x0) if (x1 - x0) != 0 else 0
            y0 = (1 - get_point(i - 1)) * height
            y1 = (1 - get_point(i)) * height
            y2 = (1 - get_point(i + 1)) * height
            y3 = (1 - get_point(i + 2)) * height
            linear_py = lerp(y1, y2, t)
            smooth_py = catmull_rom(y0, y1, y2, y3, t)
            py = lerp(linear_py, smooth_py, smoothing) + y
            yield px, py
            j += 1

        # Ensure the last point of the segment is included
        t = 1.0
        y0 = (1 - get_point(i - 1)) * height
        y1 = (1 - get_point(i)) * height
        y2 = (1 - get_point(i + 1)) * height
        y3 = (1 - get_point(i + 2)) * height
        linear_py = lerp(y1, y2, t)
        smooth_py = catmull_rom(y0, y1, y2, y3, t)
        py = lerp(linear_py, smooth_py, smoothing) + y
        yield x1, py


@micropython.viper
def _curve_cols_viper(yfp: ptr32, npts: int, out: ptr32, ncols: int, y_origin: int, smoothing_fp: int):
    """Integer Catmull-Rom: fill out[0..ncols-1] with the curve's top y
    per pixel column.

    yfp holds npts+2 entries of 8.8 fixed-point (1-value)*height with the
    endpoints duplicated (so segment i reads yfp[i..i+3] without bounds
    branches). t runs 0..256 within a segment; the column->segment
    mapping is exact rational math (c*nseg/width), so no drift
    accumulates across segments. smoothing_fp is smoothing*256.
    """
    width = ncols - 1
    nseg = npts - 1
    last_i = -1
    p1 = 0
    p2 = 0
    c0 = 0
    c1 = 0
    c2 = 0
    c3 = 0
    for c in range(ncols):
        scaled = c * nseg
        i = scaled // width
        if i > nseg - 1:
            i = nseg - 1
        t = ((scaled - i * width) << 8) // width
        if t > 256:
            t = 256
        if i != last_i:
            p0 = yfp[i]
            p1 = yfp[i + 1]
            p2 = yfp[i + 2]
            p3 = yfp[i + 3]
            c0 = 2 * p1
            c1 = p2 - p0
            c2 = 2 * p0 - 5 * p1 + 4 * p2 - p3
            c3 = 3 * (p1 - p2) + p3 - p0
            last_i = i
        # Horner form with a >>8 after each multiply keeps every
        # intermediate under 2^31 for height <= 512 (32-bit viper ints)
        acc = ((c3 * t) >> 8) + c2
        acc = ((acc * t) >> 8) + c1
        acc = ((acc * t) >> 8) + c0
        smooth = acc >> 1
        linear = p1 + (((p2 - p1) * t) >> 8)
        py = linear + (((smooth - linear) * smoothing_fp) >> 8)
        out[c] = (py >> 8) + y_origin


# Reused across redraws (grown on demand) so computing a curve doesn't
# allocate. Only the single active display renders at a time; these are
# scratch for one draw_* call, not valid across awaits from two charts.
_cols_cache = None
_yfp_cache = None

def _compute_curve(y, width, height, points, smoothing):
    """Run the fixed-point kernel; returns an array('i') whose first
    width+1 entries are the curve's top y per pixel column."""
    global _cols_cache, _yfp_cache
    n = len(points)
    ncols = width + 1

    cols = _cols_cache
    if cols is None or len(cols) < ncols:
        cols = array('i', (0 for _ in range(ncols)))
        _cols_cache = cols

    yfp = _yfp_cache
    if yfp is None or len(yfp) < n + 2:
        yfp = array('i', (0 for _ in range(n + 2)))
        _yfp_cache = yfp

    # 8.8 fixed point, clamped non-negative: viper reads these through
    # ptr32, which is unsigned on 64-bit builds
    hfp = height * 256.0
    for k in range(n):
        v = int(hfp - points[k] * hfp)
        yfp[k + 1] = v if v > 0 else 0
    yfp[0] = yfp[1]
    yfp[n + 1] = yfp[n]

    _curve_cols_viper(yfp, n, cols, ncols, y, int(smoothing * 256))
    return cols


def compute_column_width(width, num_points):
    if num_points <= 1:
        return width
    return width / (num_points - 1)


def map_px_to_index(px, x, width, num_points):
    if num_points <= 0:
        return 0
    column_width = compute_column_width(width, num_points)
    # Translate px relative to the chart origin x
    relative_px = max(0.0, px - x)
    index = int(relative_px / column_width)
    if index < 0:
        return 0
    if index >= num_points:
        return num_points - 1
    return index


async def draw_segmented_area(display, x, y, width, height, raw_values, normalized_values, color_fn, step=1, smoothing=1.0, alpha_divisor=2):
    if not normalized_values or not raw_values or len(normalized_values) != len(raw_values):
        return
    num_points = len(raw_values)
    if width <= 0 or num_points < 2:
        return

    cols = _compute_curve(y, width, height, normalized_values, smoothing)
    baseline_y = y + height
    max_index = num_points - 1
    d = alpha_divisor if alpha_divisor > 1 else 1

    # color_fn is assumed pure: it's only re-run when the data index
    # under the column changes, not per column
    last_index = -1
    color = 0
    last_c = None
    for c in range(0, width + 1, step):
        data_index = (c * max_index) // width
        if data_index != last_index:
            base = color_fn(data_index, raw_values[data_index])
            # Dim RGB color by divisor
            r = (base >> 16) & 0xFF
            g = (base >> 8) & 0xFF
            b = base & 0xFF
            color = ((r // d) << 16) | ((g // d) << 8) | (b // d)
            last_index = data_index

        top_y = cols[c]
        rect_height = baseline_y - top_y
        if rect_height > 0:
            # Vertical strip of the area under the curve, covering any
            # columns skipped by step
            if last_c is None:
                display.rect(x + c, top_y, 1, rect_height, color, True)
            else:
                display.rect(x + last_c + 1, top_y, c - last_c, rect_height, color, True)
        last_c = c

        # Yield often enough to keep other tasks live, but not per
        # column -- the scheduler round-trip dwarfs the drawing
        if (c & 15) == 15:
            await asyncio.sleep(0)


async def draw_colored_points(display, x, y, width, height, raw_values, normalized_values, color_fn, radius=2, step=1, smoothing=1.0):
    if not normalized_values or not raw_values or len(normalized_values) != len(raw_values):
        return
    num_points = len(raw_values)
    if width <= 0 or num_points < 2:
        return

    cols = _compute_curve(y, width, height, normalized_values, smoothing)
    max_index = num_points - 1
    r = int(radius)

    last_index = -1
    color = 0
    for c in range(0, width + 1, step):
        data_index = (c * max_index) // width
        if data_index != last_index:
            color = color_fn(data_index, raw_values[data_index])
            last_index = data_index
        display.ellipse(x + c, cols[c], r, r, color, True)
        if (c & 15) == 15:
            await asyncio.sleep(0)
