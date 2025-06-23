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

def draw_chart(display, x, y, width, height, points):
    def get_point(idx):
        if idx < 0:
            return points[0]
        elif idx >= len(points):
            return points[-1]
        else:
            return points[idx]

    if len(points) < 2:
        return  # Not enough points to draw

    column_width = width / (len(points) - 1)  # Use float division for accuracy

    for i in range(len(points) - 1):
        x0 = int(x + i * column_width)
        x1 = int(x + (i + 1) * column_width)
        if x1 == x0:
            x1 += 1  # Ensure at least one pixel width
        for px in range(x0, x1):
            t = (px - x0) / (x1 - x0) if (x1 - x0) != 0 else 0
            y0 = (1 - get_point(i - 1)) * height
            y1 = (1 - get_point(i)) * height
            y2 = (1 - get_point(i + 1)) * height
            y3 = (1 - get_point(i + 2)) * height
            py = int(catmull_rom(y0, y1, y2, y3, t) + y)
            yield px, py
