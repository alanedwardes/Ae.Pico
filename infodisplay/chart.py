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

    ptr8 = ptr16 = ptr32 = object

    def _as_ptr8(obj):
        if hasattr(obj, '_framebuffer'): return memoryview(obj._framebuffer).cast('B')
        if hasattr(obj, '_buf'): return memoryview(obj._buf).cast('B')
        return memoryview(obj).cast('B')

    def _as_ptr16(obj):
        if hasattr(obj, '_framebuffer'): return memoryview(obj._framebuffer).cast('H')
        if hasattr(obj, '_buf'): return memoryview(obj._buf).cast('H')
        return memoryview(obj).cast('H')
else:
    def _as_ptr8(obj):
        if hasattr(obj, '_framebuffer'): return obj._framebuffer
        if hasattr(obj, '_buf'): return obj._buf
        return obj
    _as_ptr16 = _as_ptr8

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
    per pixel column, in 8.8 fixed point (screen-absolute, clamped
    non-negative so ptr32 readers stay unsigned-safe).

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
        if py < 0:
            py = 0
        out[c] = py + (y_origin << 8)


# Reused across redraws (grown on demand) so computing a curve doesn't
# allocate. Only the single active display renders at a time; these are
# scratch for one draw_* call, not valid across awaits from two charts.
_cols_cache = None
_yfp_cache = None

def _compute_curve(y, width, height, points, smoothing):
    """Run the fixed-point kernel; returns an array('i') whose first
    width+1 entries are the curve's top y per pixel column in 8.8 fixed
    point (screen-absolute)."""
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


# _RENDER_PARAMS layout (non-negative values only: read via ptr32,
# unsigned on 64-bit builds):
#  0 c0  1 c1     global column range [c0, c1)
#  2 x            chart x origin (px)
#  3 fbh  4 ybase (px; area fills down to ybase-1)
#  5 has_line  6 rq (line half-height, Q8)  7 has_area
#  8 bpp  9 fbw  10 stride (bytes)
# 11..13 line r,g,b  14..16 area r,g,b
# 17 line packed  18 area packed
#
# Scratch: only the single active display renders at a time
_render_params = array('i', (0 for _ in range(19)))


@micropython.viper
def _render_cols_viper(dest8: ptr8, dest16: ptr16, cols: ptr32, p: ptr32):
    """Columnar renderer with anti-aliased edges.

    Per column the layer stack is closed-form: the area fill runs from
    the curve down to the baseline (its top pixel gets the fractional
    coverage the curve kernel provides), and the line is a vertical band
    around the curve, extended to the previous column's y so steep
    segments stay connected. Partial-coverage pixels read-modify-write
    blend against whatever is already in the framebuffer, so the line's
    lower fringe blends into the area fill and the upper into the
    background regardless of which layers a caller enables.
    """
    c0 = int(p[0]); c1 = int(p[1]); x = int(p[2])
    fbh = int(p[3]); ybase = int(p[4])
    has_line = int(p[5]); rq = int(p[6]); has_area = int(p[7])
    bpp = int(p[8]); fbw = int(p[9]); stride = int(p[10])

    c = c0
    while c < c1:
        yq = int(cols[c])
        xpix = x + c
        if has_area != 0:
            at = yq >> 8
            if at < ybase:
                cov = 256 - (yq & 255)
                if at >= 0 and cov > 0:
                    ia = 256 - cov
                    if bpp == 2:
                        o = at * fbw + xpix
                        v = int(dest16[o])
                        r = (((v >> 8) & 0xF8) * ia + int(p[14]) * cov) >> 8
                        g = (((v >> 3) & 0xFC) * ia + int(p[15]) * cov) >> 8
                        b = (((v << 3) & 0xF8) * ia + int(p[16]) * cov) >> 8
                        dest16[o] = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
                    else:
                        o = at * stride + xpix
                        v = int(dest8[o])
                        r = ((v & 0xE0) * ia + int(p[14]) * cov) >> 8
                        g = (((v & 0x1C) << 3) * ia + int(p[15]) * cov) >> 8
                        b = (((v & 0x03) << 6) * ia + int(p[16]) * cov) >> 8
                        dest8[o] = (r & 0xE0) | ((g & 0xE0) >> 3) | ((b & 0xC0) >> 6)
                j = at + 1
                if j < 0:
                    j = 0
                if bpp == 2:
                    a_pack = int(p[18])
                    o = j * fbw + xpix
                    while j < ybase:
                        dest16[o] = a_pack
                        o += fbw
                        j += 1
                else:
                    a_pack = int(p[18])
                    o = j * stride + xpix
                    while j < ybase:
                        dest8[o] = a_pack
                        o += stride
                        j += 1
        if has_line != 0:
            lo = yq
            hi = yq
            if c > 0:
                pq = int(cols[c - 1])
                if pq < lo:
                    lo = pq
                elif pq > hi:
                    hi = pq
            lt = lo - rq
            lb = hi + rq
            jt = lt >> 8
            jb = lb >> 8
            # Fringe rows blend, interior rows overwrite
            j = jt
            while j <= jb:
                if j == jt or j == jb:
                    if jt == jb:
                        cov = lb - lt
                    elif j == jt:
                        cov = 256 - (lt & 255)
                    else:
                        cov = lb & 255
                else:
                    cov = 256
                if 0 <= j < fbh and cov > 0:
                    if cov >= 256:
                        if bpp == 2:
                            dest16[j * fbw + xpix] = int(p[17])
                        else:
                            dest8[j * stride + xpix] = int(p[17])
                    else:
                        ia = 256 - cov
                        if bpp == 2:
                            o = j * fbw + xpix
                            v = int(dest16[o])
                            r = (((v >> 8) & 0xF8) * ia + int(p[11]) * cov) >> 8
                            g = (((v >> 3) & 0xFC) * ia + int(p[12]) * cov) >> 8
                            b = (((v << 3) & 0xF8) * ia + int(p[13]) * cov) >> 8
                            dest16[o] = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
                        else:
                            o = j * stride + xpix
                            v = int(dest8[o])
                            r = ((v & 0xE0) * ia + int(p[11]) * cov) >> 8
                            g = (((v & 0x1C) << 3) * ia + int(p[12]) * cov) >> 8
                            b = (((v & 0x03) << 6) * ia + int(p[13]) * cov) >> 8
                            dest8[o] = (r & 0xE0) | ((g & 0xE0) >> 3) | ((b & 0xC0) >> 6)
                j += 1
        c += 1


def _pack_color(bpp, r, g, b):
    if bpp == 2:
        return ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
    return (r & 0xE0) | ((g & 0xE0) >> 3) | ((b & 0xC0) >> 6)


async def _render_columns(display, x, y, width, height, raw_values, normalized_values, color_fn, smoothing, has_area, alpha_divisor, has_line, radius):
    if not normalized_values or not raw_values or len(normalized_values) != len(raw_values):
        return
    num_points = len(raw_values)
    if width <= 0 or num_points < 2:
        return

    cols = _compute_curve(y, width, height, normalized_values, smoothing)
    max_index = num_points - 1
    d = alpha_divisor if alpha_divisor > 1 else 1

    fbw, fbh = display.get_bounds()
    bpp = display.bytes_per_pixel
    p = _render_params
    p[2] = x
    p[3] = fbh
    p[4] = y + height
    p[5] = 1 if has_line else 0
    p[6] = int(radius) << 8
    p[7] = 1 if has_area else 0
    p[8] = bpp
    p[9] = fbw
    p[10] = fbw * bpp
    d8 = _as_ptr8(display)
    d16 = _as_ptr16(display) if bpp == 2 else d8

    # color_fn is assumed pure: one kernel call per run of columns
    # sharing a data index, yielding to the scheduler between runs
    c = 0
    while c <= width:
        data_index = (c * max_index) // width
        c_end = ((data_index + 1) * width + max_index - 1) // max_index
        if c_end > width + 1:
            c_end = width + 1
        base = color_fn(data_index, raw_values[data_index])
        r = (base >> 16) & 0xFF
        g = (base >> 8) & 0xFF
        b = base & 0xFF
        p[0] = c
        p[1] = c_end
        p[11] = r; p[12] = g; p[13] = b
        p[14] = r // d; p[15] = g // d; p[16] = b // d
        p[17] = _pack_color(bpp, r, g, b)
        p[18] = _pack_color(bpp, r // d, g // d, b // d)
        _render_cols_viper(d8, d16, cols, p)
        c = c_end
        await asyncio.sleep(0)


async def draw_segmented_area(display, x, y, width, height, raw_values, normalized_values, color_fn, step=1, smoothing=1.0, alpha_divisor=2):
    # step is accepted for API compatibility; the columnar kernel always
    # renders every column
    await _render_columns(display, x, y, width, height, raw_values, normalized_values, color_fn, smoothing, True, alpha_divisor, False, 0)


async def draw_colored_points(display, x, y, width, height, raw_values, normalized_values, color_fn, radius=2, step=1, smoothing=1.0):
    await _render_columns(display, x, y, width, height, raw_values, normalized_values, color_fn, smoothing, False, 1, True, radius)
