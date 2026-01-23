import asyncio

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

    baseline_y = y + height
    last_x_int = None
    num_points = len(raw_values)
    if width <= 0 or num_points <= 0:
        return
    max_index = num_points - 1

    for px, py in draw_chart(x, y, width, height, normalized_values, step=step, smoothing=smoothing):
        x_int = int(px)

        if last_x_int is not None and x_int <= last_x_int:
            continue

        # Integer mapping from pixel x to data index to avoid float division churn
        rel_px = x_int - x
        if rel_px < 0:
            rel_px = 0
        data_index = (rel_px * max_index) // width
        if data_index > max_index:
            data_index = max_index
        color = color_fn(data_index, raw_values[data_index])
        # Dim RGB565 color by divisor
        d = max(1, alpha_divisor)
        r5 = (color >> 11) & 0x1F
        g6 = (color >> 5) & 0x3F
        b5 = color & 0x1F
        r5 //= d
        g6 //= d
        b5 //= d
        transparent_color = (r5 << 11) | (g6 << 5) | b5

        rect_width = 1 if last_x_int is None else max(1, x_int - last_x_int)
        top_y = int(py)
        rect_height = max(0, baseline_y - top_y)
        # Draw a vertical strip representing the area under the curve
        draw_x = x_int if last_x_int is None else (last_x_int + 1)
        display.rect(draw_x, top_y, rect_width, rect_height, transparent_color, True)

        last_x_int = x_int
        await asyncio.sleep(0)


async def draw_colored_points(display, x, y, width, height, raw_values, normalized_values, color_fn, radius=2, step=1, smoothing=1.0):
    if not normalized_values or not raw_values or len(normalized_values) != len(raw_values):
        return
    num_points = len(raw_values)
    if width <= 0 or num_points <= 0:
        return
    max_index = num_points - 1
    for px, py in draw_chart(x, y, width, height, normalized_values, step=step, smoothing=smoothing):
        x_int = int(px)
        rel_px = x_int - x
        if rel_px < 0:
            rel_px = 0
        data_index = (rel_px * max_index) // width
        if data_index > max_index:
            data_index = max_index
        color = color_fn(data_index, raw_values[data_index])
        display.ellipse(int(px), int(py), int(radius), int(radius), color, True)
        await asyncio.sleep(0)