import array

def catmull_rom(p0, p1, p2, p3, t):
    t2 = t * t
    t3 = t2 * t
    return 0.5 * (
        (2 * p1) +
        (-p0 + p2) * t +
        (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2 +
        (-p0 + 3 * p1 - 3 * p2 + p3) * t3
    )

def lerp(a, b, t):
    return a + (b - a) * t

def generate_spline_points(x, y, width, height, points, step=4, smoothing=1.0):
    """
    Generates a list of (x, y) points for the spline curve.
    Significantly reduces overhead by only calculating points every `step` pixels.
    """
    if len(points) < 2:
        return []

    curve_points = []
    num_points = len(points)
    column_width = width / (num_points - 1)
    
    # Pre-calculate scaled y values to avoid doing it in the loop
    scaled_points = [(1 - p) * height for p in points]

    for i in range(num_points - 1):
        x0_col = x + i * column_width
        x1_col = x + (i + 1) * column_width
        
        # Determine the segment start and end in pixels
        start_px = int(x0_col)
        end_px = int(x1_col)
        
        seg_width = x1_col - x0_col
        if seg_width <= 0:
            continue

        p0 = scaled_points[max(0, i - 1)]
        p1 = scaled_points[i]
        p2 = scaled_points[min(num_points - 1, i + 1)]
        p3 = scaled_points[min(num_points - 1, i + 2)]

        # Iterate through pixels in this segment with the given step
        current_x = start_px
        
        # Ensure we don't duplicate points but cover the range
        # We start at start_px.
        
        while current_x < x1_col:
            # Local t for spline
            t = (current_x - x0_col) / seg_width
            
            # Clamp t
            if t < 0: t = 0
            elif t > 1: t = 1
            
            linear_py = lerp(p1, p2, t)
            smooth_py = catmull_rom(p0, p1, p2, p3, t)
            py = lerp(linear_py, smooth_py, smoothing) + y
            
            curve_points.append((int(current_x), int(py)))
            
            current_x += step

    # Ensure the very last point is added
    last_x = int(x + width)
    last_y = int(scaled_points[-1] + y)
    
    # If the last point generated is not the end, add the end point
    if not curve_points or curve_points[-1][0] < last_x:
        curve_points.append((last_x, last_y))
        
    return curve_points

def draw_segmented_area(display, x, y, width, height, raw_values, normalized_values, color_fn, step=4, smoothing=1.0, alpha_divisor=2):
    """
    Draws a filled area chart.
    Optimized to use polygon primitives reusing a single coordinate buffer.
    """
    if not normalized_values or not raw_values or len(normalized_values) != len(raw_values):
        return
    
    # Generate the curve vertices
    curve_points = generate_spline_points(x, y, width, height, normalized_values, step, smoothing)
    if not curve_points:
        return

    baseline_y = y + height
    max_index = len(raw_values) - 1
    
    # Reusable array for polygon coordinates [x1, base, x1, y1, x2, y2, x2, base]
    # We use 'h' (signed short) which is efficient and sufficient for display coords
    poly_coords = array.array('h', [0] * 8)

    for i in range(len(curve_points) - 1):
        x1, y1 = curve_points[i]
        x2, y2 = curve_points[i+1]
        
        # Determine color for this segment (use center point logic)
        mid_x = (x1 + x2) // 2
        rel_px = mid_x - x
        if rel_px < 0: rel_px = 0
        data_index = int((rel_px * max_index) // width)
        if data_index > max_index: data_index = max_index
        
        c = color_fn(data_index, raw_values[data_index])
        
        # Apply dimming/alpha
        d = max(1, alpha_divisor)
        r5 = (c >> 11) & 0x1F
        g6 = (c >> 5) & 0x3F
        b5 = c & 0x1F
        r5 //= d
        g6 //= d
        b5 //= d
        color = (r5 << 11) | (g6 << 5) | b5
        
        # Fill poly coordinates
        # 1. Start on baseline at x1
        poly_coords[0] = x1
        poly_coords[1] = baseline_y
        # 2. Go up to curve at x1
        poly_coords[2] = x1
        poly_coords[3] = y1
        # 3. Go to curve at x2
        poly_coords[4] = x2
        poly_coords[5] = y2
        # 4. Drop to baseline at x2
        poly_coords[6] = x2
        poly_coords[7] = baseline_y
        
        # Draw filled polygon
        display.poly(0, 0, poly_coords, color, True)

import math

# ... (previous imports if any, but array is likely there)

def draw_colored_points(display, x, y, width, height, raw_values, normalized_values, color_fn, radius=2, step=1, smoothing=1.0):
    """
    Draws a line chart with variable thickness.
    Uses polygons to emulate thick lines.
    """
    if not normalized_values or not raw_values or len(normalized_values) != len(raw_values):
        return

    # Use a minimum step of 2 to ensure we reduce points, unless step is specifically 1
    curve_points = generate_spline_points(x, y, width, height, normalized_values, step, smoothing)
    
    if len(curve_points) < 2:
        return

    max_index = len(raw_values) - 1
    
    # Calculate half-width for thickness
    half_w = radius  # radius is effectively half-thickness
    if half_w < 0.5: half_w = 0.5
    
    # Reusable array for polygon coordinates (4 points * 2 coords)
    poly_coords = array.array('h', [0] * 8)
    
    for i in range(len(curve_points) - 1):
        x1, y1 = curve_points[i]
        x2, y2 = curve_points[i+1]
        
        # Color resolution
        rel_px = x1 - x
        if rel_px < 0: rel_px = 0
        data_index = int((rel_px * max_index) // width)
        if data_index > max_index: data_index = max_index
        color = color_fn(data_index, raw_values[data_index])
        
        if radius <= 0.5:
             display.line(x1, y1, x2, y2, color)
        else:
            # Calculate normals for thickness
            dx = x2 - x1
            dy = y2 - y1
            dist = math.sqrt(dx*dx + dy*dy)
            if dist == 0:
                continue
                
            # Normalized perpendicular vector (-dy, dx) scaled by half_w
            nx = (-dy * half_w) / dist
            ny = (dx * half_w) / dist
            
            # Corners
            poly_coords[0] = int(x1 + nx)
            poly_coords[1] = int(y1 + ny)
            
            poly_coords[2] = int(x2 + nx)
            poly_coords[3] = int(y2 + ny)
            
            poly_coords[4] = int(x2 - nx)
            poly_coords[5] = int(y2 - ny)
            
            poly_coords[6] = int(x1 - nx)
            poly_coords[7] = int(y1 - ny)
            
            display.poly(0, 0, poly_coords, color, True)
            
            # Draw a circle at the joints (x2, y2) to round it off? 
            # Or just rely on slight overlap. overlap is handled by ensuring segments met.
            # Ideally we'd draw a circle at x1 for the first one and x2 for all to preserve "rounded" look of original.
            # Original was just circles.
            # Let's add a circle at the start node (previous segment end handled by its poly? No, sharp corners).
            # Drawing a filled circle at x1, y1 (and last point) improves look.
            
            display.ellipse(x1, y1, int(radius), int(radius), color, True)

    # Draw the final joint/end cap
    if curve_points:
        lx, ly = curve_points[-1]
        # Resolve color for last point
        data_index = max_index # Simplified
        color = color_fn(data_index, raw_values[data_index])
        display.ellipse(lx, ly, int(radius), int(radius), color, True)

def draw_chart(x, y, width, height, points, step=1, smoothing=1.0):
    """
    Generator compatible with old API, providing pixels or points.
    Now yields points from the optimized generator.
    """
    gp = generate_spline_points(x, y, width, height, points, step, smoothing)
    for p in gp:
        yield p
