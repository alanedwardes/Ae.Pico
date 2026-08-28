import asyncio
import random


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


def _shuffle_in_place(items):
    for i in range(len(items) - 1, 0, -1):
        j = random.randint(0, i)
        items[i], items[j] = items[j], items[i]


async def draw_cells(display, cells, *, shuffle=False, clear_color=None):
    cells = list(cells)
    if shuffle:
        _shuffle_in_place(cells)
    for x, y, w, h, draw_fn, args in cells:
        if clear_color is not None:
            display.rect(int(x), int(y), int(w), int(h), clear_color, True)
        await draw_fn(display, x, y, w, h, *args)
        await asyncio.sleep(0)
