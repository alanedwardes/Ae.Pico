"""Anti-aliased gauge rendering in a single scanline pass.

The gauge is one closed-form shape: an annular arc with round caps,
plus up to three marker discs (secondary marker, notch outline, notch
fill). The arc is always symmetric about the vertical axis through the
centre, so folding x -> |x - cx| maps both caps onto one and reduces
the angular gap test to a per-row threshold on |x - cx| -- no atan2,
no blackout polygon, no cap circles nudged flush with epsilon offsets.

Anti-aliasing is nearly free because the callers clear the region to
black first: pixel coverage just scales the layer colour (no
read-modify-write against the framebuffer), and edge coverage comes
from the squared distance already in hand (alpha ~ (r_edge^2 - d^2) /
2r), so the inner loop needs no sqrt and no trig. Fixed point
throughout: coordinates Q4 (16ths of a pixel), squared distances Q8,
alpha 0..256.
"""

import math
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


@micropython.viper
def _isqrt(v: int) -> int:
    r = 0
    b = 1 << 28
    while b > v:
        b >>= 2
    while b != 0:
        t = r + b
        if v >= t:
            v -= t
            r = (r >> 1) + b
        else:
            r >>= 1
        b >>= 2
    return r


# _PARAMS layout (every value non-negative: the kernel reads them via
# ptr32, which is unsigned on 64-bit builds -- see chart.py):
#  0 y0    1 y1        row range (px, clipped to the framebuffer)
#  2 cxq   3 cyq       centre (Q4)
#  4 rmax2 5 rmin2     scanline span radii squared (Q8); rmin2 0 = no hole
#  6 stride (bytes)  7 bpp  8 fbw (px)
#  9 ro2p 10 ro2m     ring outer edge at +-0.5px, squared (Q8)
# 11 ri2p 12 ri2m     ring inner edge
# 13 inv_ro 14 amax_ro  alpha slope / full-alpha clamp, outer edge
# 15 inv_ri 16 amax_ri  inner edge (0,0 when ri < 1: everything is inside)
# 17 ex 18 ey         gap edge direction (sin, cos of gap half-angle, Q14)
# 19 capx 20 capy     cap centre in folded coords (Q4, centre-relative)
# 21..23 cap disc (r2p, inv, amax)   24 capbb (Q4 bbox half-extent)
# 25..27 groove r,g,b   28 packed groove colour (RGB565 word / 8-bit byte)
# 30 has_sec 31 sxq 32 syq  33..35 sec disc  36 secbb  37..39 sec r,g,b
# 40 has_notch 41 nxq 42 nyq  43..45 outline disc  46..48 fill disc
# 49 nbb  50..52 outline r,g,b  53..55 fill r,g,b
#
# Scratch for the kernel parameters: only the single active display
# renders at a time, so one module-level buffer is safe
_PARAMS = array('i', (0 for _ in range(56)))


@micropython.viper
def _render(dest8: ptr8, dest16: ptr16, p: ptr32):
    y0 = int(p[0]); y1 = int(p[1])
    cxq = int(p[2]); cyq = int(p[3])
    rmax2 = int(p[4]); rmin2 = int(p[5])
    stride = int(p[6]); bpp = int(p[7]); fbw = int(p[8])
    ro2p = int(p[9]); ro2m = int(p[10])
    ri2p = int(p[11]); ri2m = int(p[12])
    ex = int(p[17]); ey = int(p[18])
    capx = int(p[19]); capy = int(p[20])
    capbb = int(p[24])
    g16 = int(p[28])
    has_sec = int(p[30]); secbb = int(p[36])
    has_notch = int(p[40]); nbb = int(p[49])

    y = y0
    while y < y1:
        yq = (y << 4) + 8
        dy = yq - cyq
        dy2 = dy * dy
        if dy2 >= rmax2:
            y += 1
            continue
        half = int(_isqrt(rmax2 - dy2))
        xs = (cxq - half) >> 4
        xe = ((cxq + half) >> 4) + 1
        if xs < 0:
            xs = 0
        if xe > fbw:
            xe = fbw
        # Inner hole: skip the run of pixels that can't touch anything.
        # Shrunk a pixel each side so edge rounding stays conservative;
        # the stragglers fall through the radial tests below.
        hx0 = xe
        hx1 = xe
        if dy2 < rmin2:
            ihalf = int(_isqrt(rmin2 - dy2))
            hx0 = ((cxq - ihalf) >> 4) + 2
            hx1 = ((cxq + ihalf) >> 4) - 1
            if hx1 <= hx0:
                hx0 = xe
                hx1 = xe

        # The in-arc test ey*fx > ex*dy collapses to a per-row threshold
        # on the folded coordinate (exact: ey > 0 for any gap < 90deg)
        t = ex * dy
        fxmin = 0 if t < 0 else t // ey + 1

        # Row-level bounding boxes collapse the per-pixel proximity
        # tests to a single branch on most rows
        d = dy - capy
        if d < 0:
            d = 0 - d
        cap_row = 1 if d <= capbb else 0
        notch_row = 0
        if has_notch != 0:
            d = yq - int(p[42])
            if d < 0:
                d = 0 - d
            if d <= nbb:
                notch_row = 1
        sec_row = 0
        if has_sec != 0:
            d = yq - int(p[32])
            if d < 0:
                d = 0 - d
            if d <= secbb:
                sec_row = 1
        special = cap_row | notch_row | sec_row

        row = y * stride
        row16 = y * fbw
        x = xs
        dx = (xs << 4) + 8 - cxq
        rr = dx * dx + dy2
        while x < xe:
            if x == hx0:
                x = hx1
                if x >= xe:
                    break
                dx = (x << 4) + 8 - cxq
                rr = dx * dx + dy2
            fx = dx if dx >= 0 else 0 - dx
            near = 0
            if special != 0:
                if cap_row != 0:
                    d = fx - capx
                    if d < 0:
                        d = 0 - d
                    if d <= capbb:
                        near = 1
                if notch_row != 0:
                    d = dx + cxq - int(p[41])
                    if d < 0:
                        d = 0 - d
                    if d <= nbb:
                        near = 1
                if sec_row != 0:
                    d = dx + cxq - int(p[31])
                    if d < 0:
                        d = 0 - d
                    if d <= secbb:
                        near = 1
            if near == 0:
                # Nothing but the plain ring here: full interior, AA
                # edge band, or nothing
                if fx >= fxmin:
                    if rr < ro2m and rr > ri2p:
                        if bpp == 2:
                            dest16[row16 + x] = g16
                        else:
                            dest8[row + x] = g16
                    elif rr < ro2p and rr > ri2m:
                        d = ro2p - rr
                        a = 256 if d >= int(p[14]) else (d * int(p[13])) >> 16
                        d = rr - ri2m
                        if d < int(p[16]):
                            ai = (d * int(p[15])) >> 16
                            if ai < a:
                                a = ai
                        r = (int(p[25]) * a) >> 8
                        g = (int(p[26]) * a) >> 8
                        b = (int(p[27]) * a) >> 8
                        if bpp == 2:
                            dest16[row16 + x] = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
                        else:
                            dest8[row + x] = (r & 0xE0) | ((g & 0xE0) >> 3) | ((b & 0xC0) >> 6)
            else:
                # Full composite: ring gated by the gap, cap disc, then
                # the marker discs blended in paint order
                ag = 0
                if fx >= fxmin:
                    d = ro2p - rr
                    if d > 0:
                        a = 256 if d >= int(p[14]) else (d * int(p[13])) >> 16
                        e2 = rr - ri2m
                        if e2 > 0:
                            ag = 256 if e2 >= int(p[16]) else (e2 * int(p[15])) >> 16
                            if a < ag:
                                ag = a
                d1 = fx - capx
                d2 = dy - capy
                d = int(p[21]) - (d1 * d1 + d2 * d2)
                if d > 0:
                    a = 256 if d >= int(p[23]) else (d * int(p[22])) >> 16
                    if a > ag:
                        ag = a
                hit = ag
                r = (int(p[25]) * ag) >> 8
                g = (int(p[26]) * ag) >> 8
                b = (int(p[27]) * ag) >> 8
                if sec_row != 0:
                    d1 = dx + cxq - int(p[31])
                    d2 = yq - int(p[32])
                    d = int(p[33]) - (d1 * d1 + d2 * d2)
                    if d > 0:
                        a = 256 if d >= int(p[35]) else (d * int(p[34])) >> 16
                        hit |= a
                        ia = 256 - a
                        r = (r * ia + int(p[37]) * a) >> 8
                        g = (g * ia + int(p[38]) * a) >> 8
                        b = (b * ia + int(p[39]) * a) >> 8
                if notch_row != 0:
                    d1 = dx + cxq - int(p[41])
                    d2 = yq - int(p[42])
                    nn = d1 * d1 + d2 * d2
                    d = int(p[43]) - nn
                    if d > 0:
                        a = 256 if d >= int(p[45]) else (d * int(p[44])) >> 16
                        hit |= a
                        ia = 256 - a
                        r = (r * ia + int(p[50]) * a) >> 8
                        g = (g * ia + int(p[51]) * a) >> 8
                        b = (b * ia + int(p[52]) * a) >> 8
                    d = int(p[46]) - nn
                    if d > 0:
                        a = 256 if d >= int(p[48]) else (d * int(p[47])) >> 16
                        hit |= a
                        ia = 256 - a
                        r = (r * ia + int(p[53]) * a) >> 8
                        g = (g * ia + int(p[54]) * a) >> 8
                        b = (b * ia + int(p[55]) * a) >> 8
                if hit != 0:
                    if bpp == 2:
                        dest16[row16 + x] = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
                    else:
                        dest8[row + x] = (r & 0xE0) | ((g & 0xE0) >> 3) | ((b & 0xC0) >> 6)
            rr += (dx << 5) + 256
            dx += 16
            x += 1
        y += 1


def _disc(p, i, rq):
    # AA disc edge: alpha = clamp((r2p - d2) * inv >> 16, 0, 256), which
    # linearises coverage over the 1px edge band ((r+.5)^2 - (r-.5)^2 = 2r).
    # rq is the radius in Q4; inv = 65536/(2r) = 524288/rq, amax = 2r*256.
    p[i] = (rq + 8) * (rq + 8)
    if rq >= 16:
        p[i + 1] = 524288 // rq
        p[i + 2] = rq * 32
    else:
        p[i + 1] = 0
        p[i + 2] = 0


def _pct(minimum, maximum, value):
    span = maximum - minimum
    pct = 0.0 if span == 0 else (value - minimum) / span
    if pct < 0.0:
        return 0.0
    if pct > 1.0:
        return 1.0
    return pct


def _mode_constants(gap_map, gap_draw):
    return (int(math.sin(gap_draw) * 16384.0), int(math.cos(gap_draw) * 16384.0),
            0.5 * math.pi + gap_map, 2.0 * (math.pi - gap_map))

# The min/max gauge maps values across 65 degrees either side of
# straight down, but its visible groove has always ended ~0.1 rad past
# the mapped extremes (the legacy cap epsilon), leaving a margin of
# groove beyond the extreme notch positions. Kept as-is. The thermostat
# arc ends on the lines from the centre to the bottom corners of the
# (height-square) region -- an angle independent of the actual size.
_GAP_MAP_MIN_MAX = math.radians(65.0)
_MODE_MIN_MAX = _mode_constants(_GAP_MAP_MIN_MAX, _GAP_MAP_MIN_MAX - 0.1)
_GAP_THERMO = math.atan2(0.5, 0.4995)
_MODE_THERMO = _mode_constants(_GAP_THERMO, _GAP_THERMO)

def draw_gauge(display, position, size, minimum_temperature=None, maximum_temperature=None, current_temperature=0, secondary_temperature=None, show_min_max=True, groove_color=0x848284, notch_outline_color=0x000000, notch_fill_color=0xFFFFFF):
    # Q4 integer geometry throughout: the sizes are ratios of the region
    # height, so only the marker angles below ever touch floats (every
    # float op allocates a boxed float on MicroPython -- see chart.py)
    px = int(position[0]); py = int(position[1])
    sw = int(size[0]); sh = int(size[1])
    cxq = px * 16 + sw * 8
    cyq = py * 16 + sh * 8
    tq = (sh * 4) // 5              # thickness 0.05h

    if show_min_max:
        radq = (sh * 36) // 5       # radius 0.45h
        exq, eyq, rad_start, sweep = _MODE_MIN_MAX
    else:
        radq = sh * 8 - tq - 16     # radius 0.5h - thickness - 1
        exq, eyq, rad_start, sweep = _MODE_THERMO

    has_range = minimum_temperature is not None and maximum_temperature is not None
    has_sec = has_range and secondary_temperature is not None

    roq = radq + tq
    riq = radq - tq
    nrq = 16 + (tq * 5) // 4        # notch outline 1 + 1.25 * thickness
    srq = (tq * 3) // 4             # secondary marker 0.75 * thickness

    rmaxq = roq + 16
    rminq = riq - 16
    if has_range:
        if radq + nrq + 16 > rmaxq:
            rmaxq = radq + nrq + 16
        if radq - nrq - 16 < rminq:
            rminq = radq - nrq - 16
    if rminq < 0:
        rminq = 0

    fbw, fbh = display.get_bounds()
    bpp = display.bytes_per_pixel
    p = _PARAMS

    y0 = (cyq - rmaxq) >> 4
    y1 = ((cyq + rmaxq) >> 4) + 2
    p[0] = y0 if y0 > 0 else 0
    p[1] = y1 if y1 < fbh else fbh
    p[2] = cxq
    p[3] = cyq
    p[4] = rmaxq * rmaxq
    p[5] = rminq * rminq
    p[6] = fbw * bpp
    p[7] = bpp
    p[8] = fbw

    p[9] = (roq + 8) * (roq + 8)
    p[10] = (roq - 8) * (roq - 8)
    v = riq + 8
    p[11] = v * v if v > 0 else 0
    v = riq - 8
    p[12] = v * v if v > 0 else 0
    p[13] = 524288 // roq
    p[14] = roq * 32
    if riq >= 16:
        p[15] = 524288 // riq
        p[16] = riq * 32
    else:
        p[15] = 0
        p[16] = 0

    p[17] = exq
    p[18] = eyq
    p[19] = (radq * exq) >> 14
    p[20] = (radq * eyq) >> 14
    _disc(p, 21, tq)
    p[24] = tq + 40

    gr = (groove_color >> 16) & 0xFF
    gg = (groove_color >> 8) & 0xFF
    gb = groove_color & 0xFF
    p[25] = gr; p[26] = gg; p[27] = gb
    if bpp == 2:
        p[28] = ((gr & 0xF8) << 8) | ((gg & 0xFC) << 3) | (gb >> 3)
    else:
        p[28] = (gr & 0xE0) | ((gg & 0xE0) >> 3) | ((gb & 0xC0) >> 6)

    p[30] = 1 if has_sec else 0
    if has_sec:
        a = rad_start + _pct(minimum_temperature, maximum_temperature, secondary_temperature) * sweep
        p[31] = cxq + int(radq * math.cos(a))
        p[32] = cyq + int(radq * math.sin(a))
        _disc(p, 33, srq)
        p[36] = srq + 24
        p[37] = 0xCE; p[38] = 0xCB; p[39] = 0xCE

    p[40] = 1 if has_range else 0
    if has_range:
        a = rad_start + _pct(minimum_temperature, maximum_temperature, current_temperature) * sweep
        p[41] = cxq + int(radq * math.cos(a))
        p[42] = cyq + int(radq * math.sin(a))
        _disc(p, 43, nrq)
        _disc(p, 46, tq)
        p[49] = nrq + 24
        p[50] = (notch_outline_color >> 16) & 0xFF
        p[51] = (notch_outline_color >> 8) & 0xFF
        p[52] = notch_outline_color & 0xFF
        p[53] = (notch_fill_color >> 16) & 0xFF
        p[54] = (notch_fill_color >> 8) & 0xFF
        p[55] = notch_fill_color & 0xFF

    d8 = _as_ptr8(display)
    d16 = _as_ptr16(display) if bpp == 2 else d8
    micropython.heap_lock()
    try:
        _render(d8, d16, p)
    finally:
        micropython.heap_unlock()
