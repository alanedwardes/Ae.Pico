import sys
from array import array

try:
    import micropython
    IS_MICROPYTHON = sys.implementation.name == 'micropython'
except ImportError:
    IS_MICROPYTHON = False

if not IS_MICROPYTHON:
    class micropython:
        @staticmethod
        def viper(f): return f
        @staticmethod
        def heap_lock(): pass
        @staticmethod
        def heap_unlock(): pass

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


_PARAMS = array('i', (0 for _ in range(40)))


@micropython.viper
def _corner_alpha(adx: int, ady: int, hw: int, hh: int, r: int) -> int:
    qx = adx - (hw - r)
    qy = ady - (hh - r)
    if qx > 0 and qy > 0:
        d2 = qx * qx + qy * qy
        dist = int(_isqrt(d2)) - r
    else:
        dist = (qx if qx > qy else qy) - r
    if dist <= -8:
        return 256
    if dist >= 8:
        return 0
    return (8 - dist) * 16


@micropython.viper
def _render(dest8: ptr8, dest16: ptr16, p: ptr32):
    y0 = int(p[0]); y1 = int(p[1])
    x0 = int(p[2]); x1 = int(p[3])
    stride = int(p[4]); bpp = int(p[5]); fbw = int(p[6])
    bcx = int(p[7]); bcy = int(p[8])
    bhw = int(p[9]); bhh = int(p[10]); router = int(p[11])
    ihw = int(p[12]); ihh = int(p[13]); rinner = int(p[14])
    boundary = int(p[17])
    ncx = int(p[19]); ncy = int(p[20]); nhw = int(p[21]); nhh = int(p[22]); nrad = int(p[23])
    outr = int(p[24]); outg = int(p[25]); outb = int(p[26])
    emr = int(p[27]); emg = int(p[28]); emb = int(p[29])
    litr = int(p[30]); litg = int(p[31]); litb = int(p[32])
    segaxis = int(p[36]); segdir = int(p[37])

    outline16 = ((outr & 0xF8) << 8) | ((outg & 0xFC) << 3) | (outb >> 3)
    lit16 = ((litr & 0xF8) << 8) | ((litg & 0xFC) << 3) | (litb >> 3)
    empty16 = ((emr & 0xF8) << 8) | ((emg & 0xFC) << 3) | (emb >> 3)
    outline8 = (outr & 0xE0) | ((outg & 0xE0) >> 3) | ((outb & 0xC0) >> 6)
    lit8 = (litr & 0xE0) | ((litg & 0xE0) >> 3) | ((litb & 0xC0) >> 6)
    empty8 = (emr & 0xE0) | ((emg & 0xE0) >> 3) | ((emb & 0xC0) >> 6)

    bxflat = bhw - router - 8
    byflat = bhh - router - 8
    ixflat = ihw - rinner - 8
    iyflat = ihh - rinner - 8
    nxflat = nhw - nrad - 8
    nyflat = nhh - nrad - 8

    y = y0
    while y < y1:
        yq = (y << 4) + 8
        dby = yq - bcy
        ady = dby if dby >= 0 else 0 - dby
        dny = yq - ncy
        adyn = dny if dny >= 0 else 0 - dny

        outer_row_visible = 1 if ady - bhh < 8 else 0
        nub_row_visible = 1 if adyn - nhh < 8 else 0

        if outer_row_visible == 0 and nub_row_visible == 0:
            y += 1
            continue

        outer_row_flat_y = 1 if ady <= byflat else 0
        inner_row_visible = 1 if ady - ihh < 8 else 0
        inner_row_flat_y = 1 if ady <= iyflat else 0
        nub_row_flat_y = 1 if adyn <= nyflat else 0

        row_fill_state = 2
        row_fa = 256
        if segaxis == 1:
            diff = (boundary - yq) if segdir == 0 else (yq - boundary)
            if diff >= 8:
                row_fill_state = 2
            elif diff <= -8:
                row_fill_state = 0
            else:
                row_fill_state = 1
                row_fa = (diff + 8) * 16

        row = y * stride
        row16 = y * fbw
        x = x0
        while x < x1:
            xq = (x << 4) + 8
            dbx = xq - bcx
            adx = dbx if dbx >= 0 else 0 - dbx

            ao = 0
            if outer_row_visible != 0:
                if outer_row_flat_y != 0:
                    if adx <= bhw - 8:
                        ao = 256
                    elif adx >= bhw + 8:
                        ao = 0
                    else:
                        ao = (8 - (adx - bhw)) * 16
                elif adx <= bxflat:
                    if ady <= bhh - 8:
                        ao = 256
                    elif ady >= bhh + 8:
                        ao = 0
                    else:
                        ao = (8 - (ady - bhh)) * 16
                else:
                    ao = int(_corner_alpha(adx, ady, bhw, bhh, router))

            na = 0
            if nub_row_visible != 0:
                dnx = xq - ncx
                adnx = dnx if dnx >= 0 else 0 - dnx
                if nub_row_flat_y != 0:
                    if adnx <= nhw - 8:
                        na = 256
                    elif adnx >= nhw + 8:
                        na = 0
                    else:
                        na = (8 - (adnx - nhw)) * 16
                elif adnx <= nxflat:
                    if adyn <= nhh - 8:
                        na = 256
                    elif adyn >= nhh + 8:
                        na = 0
                    else:
                        na = (8 - (adyn - nhh)) * 16
                else:
                    na = int(_corner_alpha(adnx, adyn, nhw, nhh, nrad))

            if ao == 0 and na == 0:
                x += 1
                continue

            r = 0; g = 0; b = 0

            if ao == 256:
                ai = 0
                if inner_row_visible != 0:
                    if inner_row_flat_y != 0:
                        if adx <= ihw - 8:
                            ai = 256
                        elif adx >= ihw + 8:
                            ai = 0
                        else:
                            ai = (8 - (adx - ihw)) * 16
                    elif adx <= ixflat:
                        if ady <= ihh - 8:
                            ai = 256
                        elif ady >= ihh + 8:
                            ai = 0
                        else:
                            ai = (8 - (ady - ihh)) * 16
                    else:
                        ai = int(_corner_alpha(adx, ady, ihw, ihh, rinner))

                if ai == 256:
                    fa = row_fa
                    if segaxis == 0:
                        diff = (boundary - xq) if segdir == 0 else (xq - boundary)
                        if diff >= 8:
                            fa = 256
                        elif diff <= -8:
                            fa = 0
                        else:
                            fa = (diff + 8) * 16
                    elif row_fill_state != 1:
                        fa = 256 if row_fill_state == 2 else 0

                    if fa == 256 and na == 0:
                        if bpp == 2:
                            dest16[row16 + x] = lit16
                        else:
                            dest8[row + x] = lit8
                        x += 1
                        continue
                    elif fa == 0 and na == 0:
                        if bpp == 2:
                            dest16[row16 + x] = empty16
                        else:
                            dest8[row + x] = empty8
                        x += 1
                        continue
                    elif fa == 256:
                        r = litr; g = litg; b = litb
                    elif fa == 0:
                        r = emr; g = emg; b = emb
                    else:
                        fia = 256 - fa
                        r = ((litr * fa) + (emr * fia)) >> 8
                        g = ((litg * fa) + (emg * fia)) >> 8
                        b = ((litb * fa) + (emb * fia)) >> 8
                elif ai == 0:
                    if na == 0:
                        if bpp == 2:
                            dest16[row16 + x] = outline16
                        else:
                            dest8[row + x] = outline8
                        x += 1
                        continue
                    r = outr; g = outg; b = outb
                else:
                    fa = row_fa
                    if segaxis == 0:
                        diff = (boundary - xq) if segdir == 0 else (xq - boundary)
                        if diff >= 8:
                            fa = 256
                        elif diff <= -8:
                            fa = 0
                        else:
                            fa = (diff + 8) * 16
                    elif row_fill_state != 1:
                        fa = 256 if row_fill_state == 2 else 0
                    fia = 256 - fa
                    sr = ((litr * fa) + (emr * fia)) >> 8
                    sg = ((litg * fa) + (emg * fia)) >> 8
                    sb = ((litb * fa) + (emb * fia)) >> 8
                    ia = 256 - ai
                    r = ((sr * ai) + (outr * ia)) >> 8
                    g = ((sg * ai) + (outg * ia)) >> 8
                    b = ((sb * ai) + (outb * ia)) >> 8
            else:
                r = (outr * ao) >> 8
                g = (outg * ao) >> 8
                b = (outb * ao) >> 8

            if na != 0:
                ia = 256 - na
                r = ((outr * na) + (r * ia)) >> 8
                g = ((outg * na) + (g * ia)) >> 8
                b = ((outb * na) + (b * ia)) >> 8

            if bpp == 2:
                dest16[row16 + x] = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
            else:
                dest8[row + x] = (r & 0xE0) | ((g & 0xE0) >> 3) | ((b & 0xC0) >> 6)
            x += 1
        y += 1


_GREEN = 0x00FC00
_YELLOW = 0xFFFF00
_RED = 0xF80000


def _default_lit_color(percentage):
    if percentage is None:
        return _RED
    if percentage >= 50:
        return _GREEN
    if percentage >= 20:
        return _YELLOW
    return _RED


def _clamp_pct(percentage):
    if percentage is None:
        return 0
    pct = int(percentage)
    if pct < 0:
        return 0
    if pct > 100:
        return 100
    return pct


def draw_battery(display, position, size, percentage=None, lit_color=None,
                  outline_color=0x555555, empty_color=0x252525,
                  orientation='right'):
    px = int(position[0]); py = int(position[1])
    w = int(size[0]); h = int(size[1])
    horizontal = orientation in ('right', 'left')
    across = h if horizontal else w
    length_total = w if horizontal else h

    nub_w = max(2, across // 10)
    nub_h = max(4, (across * 5) // 10)
    body_len = length_total - nub_w
    if body_len < across:
        body_len = across if length_total >= across else length_total
        nub_w = length_total - body_len
        if nub_w < 0:
            nub_w = 0

    router = min(across, body_len) // 6
    if router < 2:
        router = 2
    thickness = max(2, across // 10)
    if thickness * 2 >= min(across, body_len):
        thickness = min(across, body_len) // 3
    if thickness < 1:
        thickness = 1

    along_half_q = body_len * 8
    across_half_q = across * 8
    routerq = router * 16
    thicknessq = thickness * 16
    ia_in = along_half_q - thicknessq
    ac_in = across_half_q - thicknessq
    rinnerq = routerq - thicknessq
    if rinnerq < 0:
        rinnerq = 0
    if ia_in < 0:
        ia_in = 0
    if ac_in < 0:
        ac_in = 0

    across_center_q = (py * 16 + h * 8) if horizontal else (px * 16 + w * 8)

    if orientation == 'right':
        along_center_body_q = px * 16 + body_len * 8
        along_center_nub_q = px * 16 + body_len * 16 + nub_w * 8
        iaxis0q = along_center_body_q - ia_in
        segdir = 0
        segaxis = 0
    elif orientation == 'left':
        along_center_body_q = (px + nub_w) * 16 + body_len * 8
        along_center_nub_q = px * 16 + nub_w * 8
        iaxis0q = along_center_body_q + ia_in
        segdir = 1
        segaxis = 0
    elif orientation == 'down':
        along_center_body_q = py * 16 + body_len * 8
        along_center_nub_q = py * 16 + body_len * 16 + nub_w * 8
        iaxis0q = along_center_body_q - ia_in
        segdir = 0
        segaxis = 1
    else:
        along_center_body_q = (py + nub_w) * 16 + body_len * 8
        along_center_nub_q = py * 16 + nub_w * 8
        iaxis0q = along_center_body_q + ia_in
        segdir = 1
        segaxis = 1

    if horizontal:
        bcxq = along_center_body_q; bcyq = across_center_q
        bhwq = along_half_q; bhhq = across_half_q
        ihwq = ia_in; ihhq = ac_in
        ncxq = along_center_nub_q; ncyq = across_center_q
        nhwq = nub_w * 8; nhhq = nub_h * 8
    else:
        bcyq = along_center_body_q; bcxq = across_center_q
        bhhq = along_half_q; bhwq = across_half_q
        ihhq = ia_in; ihwq = ac_in
        ncyq = along_center_nub_q; ncxq = across_center_q
        nhhq = nub_w * 8; nhwq = nub_h * 8

    pct = _clamp_pct(percentage)
    filllenq = (ia_in * 2) if pct >= 100 else (ia_in * 2 * pct) // 100

    nub_r = min(nub_w, nub_h) // 3
    nradq = nub_r * 16

    fbw, fbh = display.get_bounds()
    bpp = display.bytes_per_pixel
    p = _PARAMS

    y0 = py - 1
    y1 = py + h + 1
    x0 = px - 1
    x1 = px + w + 1
    p[0] = y0 if y0 > 0 else 0
    p[1] = y1 if y1 < fbh else fbh
    p[2] = x0 if x0 > 0 else 0
    p[3] = x1 if x1 < fbw else fbw
    p[4] = fbw * bpp
    p[5] = bpp
    p[6] = fbw

    p[7] = bcxq; p[8] = bcyq
    p[9] = bhwq; p[10] = bhhq; p[11] = routerq
    p[12] = ihwq; p[13] = ihhq; p[14] = rinnerq
    p[17] = (iaxis0q + filllenq) if segdir == 0 else (iaxis0q - filllenq)
    p[19] = ncxq; p[20] = ncyq; p[21] = nhwq; p[22] = nhhq; p[23] = nradq
    p[36] = segaxis; p[37] = segdir

    oc = outline_color
    p[24] = (oc >> 16) & 0xFF; p[25] = (oc >> 8) & 0xFF; p[26] = oc & 0xFF
    ec = empty_color
    p[27] = (ec >> 16) & 0xFF; p[28] = (ec >> 8) & 0xFF; p[29] = ec & 0xFF
    lc = lit_color if lit_color is not None else _default_lit_color(percentage)
    p[30] = (lc >> 16) & 0xFF; p[31] = (lc >> 8) & 0xFF; p[32] = lc & 0xFF

    d8 = _as_ptr8(display)
    d16 = _as_ptr16(display) if bpp == 2 else d8
    micropython.heap_lock()
    try:
        _render(d8, d16, p)
    finally:
        micropython.heap_unlock()
