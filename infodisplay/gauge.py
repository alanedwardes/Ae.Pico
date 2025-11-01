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

def draw_gauge(display, position, size, minimum_temperature=None, maximum_temperature=None, current_temperature=0, secondary_temperature=None, show_min_max=True, groove_color=0x8410, notch_outline_color=0x0000, notch_fill_color=0xFFFF):
    centre = [size[0] / 2 + position[0], size[1] / 2 + position[1]]

    guage_thickness = size[1] * 0.05
    guage_radius = (size[1] * 0.45) if show_min_max else ((size[1] * 0.5) - guage_thickness - 1)
    has_range = (minimum_temperature is not None and maximum_temperature is not None)
    
    groove_pen = groove_color

    # Outer gauge
    circle(display, centre[0], centre[1], guage_radius + guage_thickness, groove_pen)
    
    black_pen = 0x0000

    # Inner gauge
    circle(display, centre[0], centre[1], guage_radius - guage_thickness, black_pen)

    extent_x = [centre[0] - size[1] * 0.5, centre[0] + size[1] * 0.5]

    cap_top_factor = 0.8 if show_min_max else 0.9995
    polygon(display, [
        [extent_x[0], position[1] + size[1]],
        [extent_x[0], position[1] + size[1] * cap_top_factor],
        [centre[0], centre[1]],
        [extent_x[1], position[1] + size[1] * cap_top_factor],
        [extent_x[1], position[1] + size[1]]
    ], black_pen)

    degrees_offset = 65
    if not show_min_max:
        cap_y = position[1] + size[1] * cap_top_factor
        left_point = (extent_x[0], cap_y)
        right_point = (extent_x[1], cap_y)
        angle_left = math.atan2(left_point[1] - centre[1], left_point[0] - centre[0])
        angle_right = math.atan2(right_point[1] - centre[1], right_point[0] - centre[0])
        if angle_right < angle_left:
            angle_right += 2 * math.pi
        gauge_min_max_radians = [angle_left, angle_right]
    else:
        gauge_min_max_radians = [
            math.radians(90 + degrees_offset),
            math.radians(90 + 360 - degrees_offset)
        ]
    
    # Draw rounded caps aligned to blackout polygon so they sit flush, before notch so notch renders on top
    # Rounded caps
    epsilon = 0.1 if show_min_max else 0.001
    rounded_cap_start = point_on_circle(centre[0], centre[1], guage_radius, gauge_min_max_radians[0] - epsilon)
    circle(display, rounded_cap_start[0], rounded_cap_start[1], guage_thickness, groove_pen)
    rounded_cap_end = point_on_circle(centre[0], centre[1], guage_radius, gauge_min_max_radians[1] + epsilon)
    circle(display, rounded_cap_end[0], rounded_cap_end[1], guage_thickness, groove_pen)

    if has_range and secondary_temperature is not None:
        radians_secondary = get_mapped_range_value_clamped(
            [minimum_temperature, maximum_temperature],
            gauge_min_max_radians,
            secondary_temperature
        )
        notch_point_secondary = point_on_circle(centre[0], centre[1], guage_radius, radians_secondary)
        secondary_pen = 0xCE59
        circle(display, notch_point_secondary[0], notch_point_secondary[1], guage_thickness * 0.75, secondary_pen)

    if has_range:
        radians = get_mapped_range_value_clamped(
            [minimum_temperature, maximum_temperature],
            gauge_min_max_radians,
            current_temperature
        )
        notch_point = point_on_circle(centre[0], centre[1], guage_radius, radians)
        notch_outline_pen = notch_outline_color
        notch_fill_pen = notch_fill_color
        circle(display, notch_point[0], notch_point[1], 1 + guage_thickness * 1.25, notch_outline_pen)
        circle(display, notch_point[0], notch_point[1], guage_thickness, notch_fill_pen)
    
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
