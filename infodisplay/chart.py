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

    x_positions = [x + i * column_width for i in range(len(points))]

    for i in range(len(points) - 1):
        x0 = x_positions[i]
        x1 = x_positions[i + 1]
        px_range = []
        j = 0
        while True:
            px = x0 + step * j
            if px >= x1:
                break
            px_range.append(px)
            j += 1
        px_range.append(x1)  # Ensure the last point is included
        for px in px_range:
            t = (px - x0) / (x1 - x0) if (x1 - x0) != 0 else 0
            y0 = (1 - get_point(i - 1)) * height
            y1 = (1 - get_point(i)) * height
            y2 = (1 - get_point(i + 1)) * height
            y3 = (1 - get_point(i + 2)) * height
            # Linear interpolation
            linear_py = lerp(y1, y2, t)
            # Catmull-Rom interpolation
            smooth_py = catmull_rom(y0, y1, y2, y3, t)
            # Blend between linear and smooth based on smoothing parameter
            py = lerp(linear_py, smooth_py, smoothing) + y
            yield px, py


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


def draw_segmented_area(display, x, y, width, height, raw_values, normalized_values, color_fn, step=1, smoothing=1.0, alpha_divisor=2):
    if not normalized_values or not raw_values or len(normalized_values) != len(raw_values):
        return

    current_polygon = []
    current_color = None
    first_point = True

    last_px = x

    for px, py in draw_chart(x, y, width, height, normalized_values, step=step, smoothing=smoothing):
        last_px = px
        data_index = map_px_to_index(px, x, width, len(raw_values))
        color = color_fn(data_index, raw_values[data_index])

        if first_point:
            first_x = int(px)
            current_polygon.append((first_x, y + height))
            current_polygon.append((int(px), int(py)))
            current_color = color
            first_point = False
        else:
            if current_color is not None and current_color != color:
                current_polygon.append((int(px), int(py)))
                current_polygon.append((int(px), y + height))

                transparent_color = tuple(c // max(1, alpha_divisor) for c in current_color)
                display.set_pen(display.create_pen(*transparent_color))
                display.polygon(current_polygon)

                current_polygon = [(int(px), y + height), (int(px), int(py))]
                current_color = color
            else:
                current_polygon.append((int(px), int(py)))
                current_color = color

    if current_polygon:
        last_x = int(last_px)
        current_polygon.append((last_x, y + height))
        transparent_color = tuple(c // max(1, alpha_divisor) for c in current_color)
        display.set_pen(display.create_pen(*transparent_color))
        display.polygon(current_polygon)


def draw_colored_points(display, x, y, width, height, raw_values, normalized_values, color_fn, radius=2, step=1, smoothing=1.0):
    if not normalized_values or not raw_values or len(normalized_values) != len(raw_values):
        return
    for px, py in draw_chart(x, y, width, height, normalized_values, step=step, smoothing=smoothing):
        data_index = map_px_to_index(px, x, width, len(raw_values))
        color = color_fn(data_index, raw_values[data_index])
        display.set_pen(display.create_pen(*color))
        display.circle(int(px), int(py), radius)