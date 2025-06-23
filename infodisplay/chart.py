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