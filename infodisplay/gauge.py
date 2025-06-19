import math

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

def draw_text(display, text, scale, x, y, width, height):
    thickness = scale * 3
    
    display.set_thickness(math.floor(thickness))
    
    #text_height = (scale * 20) + thickness
    #half_height = text_height * 0.5

    #self.display.set_pen(self.highlight)
    #self.display.rectangle(math.floor(x), math.floor(y), math.ceil(width), math.ceil(height))

    text_width = display.measure_text(text, scale) + thickness
    text_x = width * 0.5 - text_width * 0.5
    
    half_height = height * 0.5
    
    #self.display.set_pen(self.white)
    display.text(text, math.floor(text_x + x + (thickness * 0.5)), math.floor(y + half_height + (thickness * 0.5)), scale=scale)

def circle(display, x, y, radius):
    return display.circle(int(x), int(y), int(radius))

def polygon(display, points):
    return display.polygon([(int(point[0]), int(point[1])) for point in points])

def draw_gauge(display, position, size, minimum_temperature, maximum_temperature, current_temperature):
    centre = [size[0] / 2 + position[0], size[1] / 2 + position[1]]

    guage_radius = size[1] * 0.45
    guage_thickness = size[1] * 0.05
    
    display.set_pen(display.create_pen(128, 128, 128))

    # Outer gauge
    circle(display, centre[0], centre[1], guage_radius + guage_thickness)
    
    display.set_pen(display.create_pen(0, 0, 0))

    # Inner gauge
    circle(display, centre[0], centre[1], guage_radius - guage_thickness)

    extent_x = [centre[0] - size[1] * 0.5, centre[0] + size[1] * 0.5]

    # Polygon base
    polygon(display, [
        [extent_x[0], position[1] + size[1]],
        [extent_x[0], position[1] + size[1] * 0.8],
        [centre[0], centre[1]],
        [extent_x[1], position[1] + size[1] * 0.8],
        [extent_x[1], position[1] + size[1]]
    ])

    degrees_offset = 65
    gauge_min_max_radians = [
        math.radians(90 + degrees_offset),
        math.radians(90 + 360 - degrees_offset)
    ]
    
    display.set_pen(display.create_pen(128, 128, 128))

    # Rounded cap start
    rounded_cap_start = point_on_circle(centre[0], centre[1], guage_radius, gauge_min_max_radians[0] - 0.1)
    circle(display, rounded_cap_start[0], rounded_cap_start[1], guage_thickness)

    # Rounded cap end
    rounded_cap_end = point_on_circle(centre[0], centre[1], guage_radius, gauge_min_max_radians[1] + 0.1)
    circle(display, rounded_cap_end[0], rounded_cap_end[1], guage_thickness)

    radians = get_mapped_range_value_clamped(
        [minimum_temperature, maximum_temperature],
        gauge_min_max_radians,
        current_temperature
    )
    
    notch_point = point_on_circle(centre[0], centre[1], guage_radius, radians)
    
    display.set_pen(display.create_pen(0, 0, 0))
    circle(display, notch_point[0], notch_point[1], guage_thickness * 2)
    
    display.set_pen(display.create_pen(255, 255, 255))
    circle(display, notch_point[0], notch_point[1], guage_thickness)
    
    display.set_font("sans")
    draw_text(display, f"{current_temperature:.0f}", size[1] * 0.015, position[0], position[1], size[0], size[1])
    
    display.set_font("bitmap8")
    text_y = int(position[1] + size[1] * 0.75)
    text_size_x = size[1] * 0.5
    text_size_y = size[1] * 0.1
    
    draw_text(display, f"{minimum_temperature:.0f}", math.ceil(size[1] * 0.02), extent_x[0], text_y, text_size_x, text_size_y)
    draw_text(display, f"{maximum_temperature:.0f}", math.ceil(size[1] * 0.02), centre[0], text_y, text_size_x, text_size_y)
