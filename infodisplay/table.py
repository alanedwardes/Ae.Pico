import random
from array import array


def grid_rects(x, y, width, height, rows, cols):
    row_ys = [y + (r * height) // rows for r in range(rows + 1)]
    col_xs = [x + (c * width) // cols for c in range(cols + 1)]
    return [
        (col_xs[c], row_ys[r], col_xs[c + 1] - col_xs[c], row_ys[r + 1] - row_ys[r])
        for r in range(rows)
        for c in range(cols)
    ]


def column_rects(x, width, widths, *, min_fill_width=0):
    fixed_total = sum(w for w in widths if w is not None)
    fill_width = max(min_fill_width, width - fixed_total)
    resolved = [fill_width if w is None else w for w in widths]
    rects = []
    cx = x
    for w in resolved:
        rects.append((cx, w))
        cx += w
    return rects


class CellBatch:
    def __init__(self):
        self._x = []
        self._y = []
        self._w = []
        self._h = []
        self._fn = []
        self._args = []
        self._order = array('i', [])
        self._n = 0

    def begin(self):
        self._n = 0

    def add(self, x, y, w, h, fn, args):
        n = self._n
        if n < len(self._x):
            self._x[n] = x
            self._y[n] = y
            self._w[n] = w
            self._h[n] = h
            self._fn[n] = fn
            self._args[n] = args
        else:
            self._x.append(x)
            self._y.append(y)
            self._w.append(w)
            self._h.append(h)
            self._fn.append(fn)
            self._args.append(args)
        self._n += 1


def draw_cells(display, batch, *, shuffle=False, clear_color=None):
    n = batch._n
    order = batch._order
    if len(order) < n:
        order.extend(array('i', range(len(order), n)))
    for i in range(n):
        order[i] = i
    if shuffle:
        for i in range(n - 1, 0, -1):
            j = random.randint(0, i)
            order[i], order[j] = order[j], order[i]

    x, y, w, h, fn, args = batch._x, batch._y, batch._w, batch._h, batch._fn, batch._args
    for k in range(n):
        idx = order[k]
        cx, cy, cw, ch = x[idx], y[idx], w[idx], h[idx]
        if clear_color is not None:
            display.rect(int(cx), int(cy), int(cw), int(ch), clear_color, True)
        fn[idx](display, cx, cy, cw, ch, *args[idx])
