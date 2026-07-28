import math
from array import array



def clamp(value, min_value, max_value):
    return max(min(value, max_value), min_value)

def get_range_pct(input_range, value):
    lower_bound, upper_bound = input_range
    if upper_bound - lower_bound == 0:
        return 0.0
    return (value - lower_bound) / (upper_bound - lower_bound)

def get_range_value(output_range, pct):
    lower_bound, upper_bound = output_range
    return lower_bound + pct * (upper_bound - lower_bound)

def get_mapped_range_value_clamped(input_range, output_range, value):
    clamped_pct = clamp(
        get_range_pct(input_range, value), 0.0, 1.0
    )
    return get_range_value(output_range, clamped_pct)

def point_on_circle(x, y, radius, angle):
    return (x + radius * math.cos(angle), y + radius * math.sin(angle))


def circle(display, x, y, radius, color):
    return display.ellipse(int(x), int(y), int(radius), int(radius), color, True)

def polygon(display, points, color):
    flat = []
    for point in points:
        flat.append(int(point[0]))
        flat.append(int(point[1]))
    return display.poly(0, 0, array('h', flat), color, True)

# Gauge arc extents for the show_min_max case (65 degrees either side of
# straight down), hoisted so draw_gauge doesn't recompute them per call
_RAD_MIN_MAX_START = math.radians(90 + 65)
_RAD_MIN_MAX_END = math.radians(90 + 360 - 65)

# Scratch for the blackout polygon: only the single active display
# renders at a time, so one module-level buffer is safe
_POLY_XY = array('h', (0 for _ in range(10)))

def _mapped_angle(minimum, maximum, value, rad_start, rad_end):
    span = maximum - minimum
    pct = 0.0 if span == 0 else (value - minimum) / span
    pct = clamp(pct, 0.0, 1.0)
    return rad_start + pct * (rad_end - rad_start)

def draw_gauge(display, position, size, minimum_temperature=None, maximum_temperature=None, current_temperature=0, secondary_temperature=None, show_min_max=True, groove_color=0x848284, notch_outline_color=0x000000, notch_fill_color=0xFFFFFF):
    cx = size[0] / 2 + position[0]
    cy = size[1] / 2 + position[1]

    guage_thickness = size[1] * 0.05
    guage_radius = (size[1] * 0.45) if show_min_max else ((size[1] * 0.5) - guage_thickness - 1)
    has_range = (minimum_temperature is not None and maximum_temperature is not None)

    groove_pen = groove_color

    # Outer gauge
    circle(display, cx, cy, guage_radius + guage_thickness, groove_pen)

    black_pen = 0x000000

    # Inner gauge
    circle(display, cx, cy, guage_radius - guage_thickness, black_pen)

    extent_x0 = cx - size[1] * 0.5
    extent_x1 = cx + size[1] * 0.5

    cap_top_factor = 0.8 if show_min_max else 0.9995
    bottom_y = position[1] + size[1]
    cap_y = position[1] + size[1] * cap_top_factor

    p = _POLY_XY
    p[0] = int(extent_x0); p[1] = int(bottom_y)
    p[2] = int(extent_x0); p[3] = int(cap_y)
    p[4] = int(cx);        p[5] = int(cy)
    p[6] = int(extent_x1); p[7] = int(cap_y)
    p[8] = int(extent_x1); p[9] = int(bottom_y)
    display.poly(0, 0, p, black_pen, True)

    if not show_min_max:
        angle_left = math.atan2(cap_y - cy, extent_x0 - cx)
        angle_right = math.atan2(cap_y - cy, extent_x1 - cx)
        if angle_right < angle_left:
            angle_right += 2 * math.pi
        rad_start, rad_end = angle_left, angle_right
    else:
        rad_start, rad_end = _RAD_MIN_MAX_START, _RAD_MIN_MAX_END

    # Draw rounded caps aligned to blackout polygon so they sit flush, before notch so notch renders on top
    # Rounded caps
    epsilon = 0.1 if show_min_max else 0.001
    a = rad_start - epsilon
    circle(display, cx + guage_radius * math.cos(a), cy + guage_radius * math.sin(a), guage_thickness, groove_pen)
    a = rad_end + epsilon
    circle(display, cx + guage_radius * math.cos(a), cy + guage_radius * math.sin(a), guage_thickness, groove_pen)

    if has_range and secondary_temperature is not None:
        a = _mapped_angle(minimum_temperature, maximum_temperature, secondary_temperature, rad_start, rad_end)
        secondary_pen = 0xCECBCE
        circle(display, cx + guage_radius * math.cos(a), cy + guage_radius * math.sin(a), guage_thickness * 0.75, secondary_pen)

    if has_range:
        a = _mapped_angle(minimum_temperature, maximum_temperature, current_temperature, rad_start, rad_end)
        notch_x = cx + guage_radius * math.cos(a)
        notch_y = cy + guage_radius * math.sin(a)
        circle(display, notch_x, notch_y, 1 + guage_thickness * 1.25, notch_outline_color)
        circle(display, notch_x, notch_y, guage_thickness, notch_fill_color)

    # Text rendering removed; displays are responsible for drawing text

def get_temperature_position(position, size, minimum_temperature, maximum_temperature, temperature):
    centre = [size[0] / 2 + position[0], size[1] / 2 + position[1]]
    guage_radius = size[1] * 0.45
    degrees_offset = 65
    gauge_min_max_radians = [
        math.radians(90 + degrees_offset),
        math.radians(90 + 360 - degrees_offset)
    ]
    radians = get_mapped_range_value_clamped(
        [minimum_temperature, maximum_temperature],
        gauge_min_max_radians,
        temperature
    )
    return point_on_circle(centre[0], centre[1], guage_radius, radians)
