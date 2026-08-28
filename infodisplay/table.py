import asyncio
import random


def grid_rects(x, y, width, height, rows, cols):
    """Divide (x, y, width, height) into a rows x cols grid of even cells.

    Returns a flat list of (cx, cy, cw, ch) tuples in row-major order.
    """
    row_ys = [y + (r * height) // rows for r in range(rows + 1)]
    col_xs = [x + (c * width) // cols for c in range(cols + 1)]
    return [
        (col_xs[c], row_ys[r], col_xs[c + 1] - col_xs[c], row_ys[r + 1] - row_ys[r])
        for r in range(rows)
        for c in range(cols)
    ]


def column_rects(x, width, widths, *, min_fill_width=0):
    """Resolve column x-positions/widths for a row of columns.

    widths: list of fixed pixel widths, with at most one entry as None to
    fill the remaining space after the fixed columns.

    Returns a list of (cx, cw) tuples, one per entry in widths.
    """
    fixed_total = sum(w for w in widths if w is not None)
    fill_width = max(min_fill_width, width - fixed_total)
    resolved = [fill_width if w is None else w for w in widths]
    rects = []
    cx = x
    for w in resolved:
        rects.append((cx, w))
        cx += w
    return rects


async def draw_cells(display, cells, *, shuffle=False, clear_color=None):
    """Draw a table of cells.

    cells: iterable of (x, y, w, h, draw_fn, args), where draw_fn is a
    plain async callable draw_fn(display, x, y, w, h, *args) - typically a
    single shared top-level function reused across many cells, with args
    carrying whatever per-cell data it needs (text, color, ...).

    If shuffle is True, cells are drawn in random order rather than the
    order given - useful for an "assembling" animation effect.
    If clear_color is set, each cell's rect is filled with that color
    before its draw_fn runs.
    """
    cells = list(cells)
    if shuffle:
        random.shuffle(cells)
    for x, y, w, h, draw_fn, args in cells:
        if clear_color is not None:
            display.rect(int(x), int(y), int(w), int(h), clear_color, True)
        await draw_fn(display, x, y, w, h, *args)
        await asyncio.sleep(0)
