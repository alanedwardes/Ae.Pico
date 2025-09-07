import math
import textbox

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


def circle(display, x, y, radius):
    return display.circle(int(x), int(y), int(radius))

def polygon(display, points):
    return display.polygon([(int(point[0]), int(point[1])) for point in points])

def _draw_gauge_core(display, position, size, minimum_temperature, maximum_temperature, primary_temperature, primary_decimals=0, secondary_temperature=None, secondary_decimals=0, show_min_max=True, groove_color=(128, 128, 128), notch_outline_color=(0, 0, 0), notch_fill_color=(255, 255, 255)):
    centre = [size[0] / 2 + position[0], size[1] / 2 + position[1]]

    guage_thickness = size[1] * 0.05
    guage_radius = (size[1] * 0.45) if show_min_max else ((size[1] * 0.5) - guage_thickness - 1)
    has_range = (minimum_temperature is not None and maximum_temperature is not None)
    
    display.set_pen(display.create_pen(groove_color[0], groove_color[1], groove_color[2]))

    # Outer gauge
    circle(display, centre[0], centre[1], guage_radius + guage_thickness)
    
    display.set_pen(display.create_pen(0, 0, 0))

    # Inner gauge
    circle(display, centre[0], centre[1], guage_radius - guage_thickness)

    extent_x = [centre[0] - size[1] * 0.5, centre[0] + size[1] * 0.5]

    cap_top_factor = 0.8 if show_min_max else 0.9995
    polygon(display, [
        [extent_x[0], position[1] + size[1]],
        [extent_x[0], position[1] + size[1] * cap_top_factor],
        [centre[0], centre[1]],
        [extent_x[1], position[1] + size[1] * cap_top_factor],
        [extent_x[1], position[1] + size[1]]
    ])

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
    display.set_pen(display.create_pen(groove_color[0], groove_color[1], groove_color[2]))
    epsilon = 0.1 if show_min_max else 0.001
    rounded_cap_start = point_on_circle(centre[0], centre[1], guage_radius, gauge_min_max_radians[0] - epsilon)
    circle(display, rounded_cap_start[0], rounded_cap_start[1], guage_thickness)
    rounded_cap_end = point_on_circle(centre[0], centre[1], guage_radius, gauge_min_max_radians[1] + epsilon)
    circle(display, rounded_cap_end[0], rounded_cap_end[1], guage_thickness)

    if has_range and secondary_temperature is not None:
        radians_secondary = get_mapped_range_value_clamped(
            [minimum_temperature, maximum_temperature],
            gauge_min_max_radians,
            secondary_temperature
        )
        notch_point_secondary = point_on_circle(centre[0], centre[1], guage_radius, radians_secondary)
        display.set_pen(display.create_pen(200, 200, 200))
        circle(display, notch_point_secondary[0], notch_point_secondary[1], guage_thickness * 0.75)

    if has_range:
        radians = get_mapped_range_value_clamped(
            [minimum_temperature, maximum_temperature],
            gauge_min_max_radians,
            primary_temperature
        )
        notch_point = point_on_circle(centre[0], centre[1], guage_radius, radians)
        display.set_pen(display.create_pen(notch_outline_color[0], notch_outline_color[1], notch_outline_color[2]))
        circle(display, notch_point[0], notch_point[1], 1 + guage_thickness * 1.25)
        display.set_pen(display.create_pen(notch_fill_color[0], notch_fill_color[1], notch_fill_color[2]))
        circle(display, notch_point[0], notch_point[1], guage_thickness)
        # Reset pen to white for text and other UI elements
        display.set_pen(display.create_pen(255, 255, 255))
    
    primary_scale = size[1] * (0.015 if secondary_temperature is None else 0.010)
    primary_height = size[1] if secondary_temperature is None else size[1] * 0.85
    textbox.draw_textbox(display, f'{primary_temperature:.{primary_decimals}f}', position[0], position[1], size[0], primary_height, font='sans', scale=primary_scale)
    
    if secondary_temperature is not None:
        secondary_text_y = position[1] + size[1] * 0.65
        secondary_text_height = size[1] * 0.2
        textbox.draw_textbox(display, f'{secondary_temperature:.{secondary_decimals}f}', position[0], secondary_text_y, size[0], secondary_text_height, font='sans', scale=size[1] * 0.006)

    

    if has_range and show_min_max:
        text_y = int(position[1] + size[1] * 0.75)
        text_size_x = size[1] * 0.5
        text_scale = max(1, math.ceil(size[1] * 0.02))
        text_height = 8 * text_scale  # bitmap8 font height
        text_size_y = text_height + 4  # Add some padding
        textbox.draw_textbox(display, f'{minimum_temperature:.0f}', extent_x[0], text_y, text_size_x, text_size_y, font='bitmap8', scale=text_scale)
        textbox.draw_textbox(display, f'{maximum_temperature:.0f}', centre[0], text_y, text_size_x, text_size_y, font='bitmap8', scale=text_scale)

def draw_gauge(display, position, size, minimum_temperature=None, maximum_temperature=None, current_temperature=0, primary_decimals=0, show_min_max=True, groove_color=(128,128,128), notch_outline_color=(0,0,0), notch_fill_color=(255,255,255)):
    _draw_gauge_core(display, position, size, minimum_temperature, maximum_temperature, current_temperature, primary_decimals, None, 0, show_min_max, groove_color, notch_outline_color, notch_fill_color)
    
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

def draw_gauge_with_secondary(display, position, size, minimum_temperature=None, maximum_temperature=None, current_temperature=0, secondary_temperature=0, primary_decimals=0, secondary_decimals=0, show_min_max=True, groove_color=(128,128,128), notch_outline_color=(0,0,0), notch_fill_color=(255,255,255)):
    _draw_gauge_core(display, position, size, minimum_temperature, maximum_temperature, current_temperature, primary_decimals, secondary_temperature, secondary_decimals, show_min_max, groove_color, notch_outline_color, notch_fill_color)