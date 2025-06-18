import math
import utime
import asyncio

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

def get_mapped_range_value_unclamped(input_range, output_range, value):
    return get_range_value(output_range, get_range_pct(input_range, value))

def point_on_circle(x, y, radius, angle):
    return (x + radius * math.cos(angle), y + radius * math.sin(angle));

class TemperatureDisplay:
    def __init__(self, display, hass, entity_ids):
        self.display = display
        self.hass = hass
        self.entity_ids = entity_ids

        self.display_width, self.display_height = self.display.get_bounds()
        
        self.entities = dict()
        self.alpha = 0
        
    def draw_text(self, text, scale, x, y, width, height):
        thickness = scale * 3
        
        self.display.set_thickness(math.floor(thickness))
        
        #text_height = (scale * 20) + thickness
        #half_height = text_height * 0.5

        #self.display.set_pen(self.highlight)
        #self.display.rectangle(math.floor(x), math.floor(y), math.ceil(width), math.ceil(height))

        text_width = self.display.measure_text(text, scale) + thickness
        text_x = width * 0.5 - text_width * 0.5
        
        half_height = height * 0.5
        
        #self.display.set_pen(self.white)
        self.display.text(text, math.floor(text_x + x + (thickness * 0.5)), math.floor(y + half_height + (thickness * 0.5)), scale=scale)
    
    CREATION_PRIORITY = 1
    def create(provider):
        return TemperatureDisplay(provider['display'], provider['hassws.HassWs'], provider['config']['temperature'])
    
    def entity_updated(self, entity_id, entity):
        self.entities[entity_id] = entity
        self.update()
    
    async def start(self):
        await self.hass.subscribe(self.entity_ids.values(), self.entity_updated)
        await asyncio.Event().wait()
        
    def circle(self, x, y, radius):
        return self.display.circle(int(x), int(y), int(radius))
    
    def polygon(self, points):
        return self.display.polygon([(int(point[0]), int(point[1])) for point in points])
        
    def draw_gauge(self, position, size, minimum_temperature, maximum_temperature, current_temperature):
        centre = [size[0] / 2 + position[0], size[1] / 2 + position[1]]

        guage_radius = size[1] * 0.45
        guage_thickness = size[1] * 0.05
        
        self.display.set_pen(self.display.create_pen(128, 128, 128))

        # Outer gauge
        self.circle(centre[0], centre[1], guage_radius + guage_thickness)
        
        self.display.set_pen(self.display.create_pen(0, 0, 0))

        # Inner gauge
        self.circle(centre[0], centre[1], guage_radius - guage_thickness)

        extent_x = [centre[0] - size[1] * 0.5, centre[0] + size[1] * 0.5]

        # Polygon base
        self.polygon([
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
        
        self.display.set_pen(self.display.create_pen(128, 128, 128))

        # Rounded cap start
        rounded_cap_start = point_on_circle(centre[0], centre[1], guage_radius, gauge_min_max_radians[0] - 0.1)
        self.circle(rounded_cap_start[0], rounded_cap_start[1], guage_thickness)

        # Rounded cap end
        rounded_cap_end = point_on_circle(centre[0], centre[1], guage_radius, gauge_min_max_radians[1] + 0.1)
        self.circle(rounded_cap_end[0], rounded_cap_end[1], guage_thickness)

        radians = get_mapped_range_value_clamped(
            [minimum_temperature, maximum_temperature],
            gauge_min_max_radians,
            current_temperature
        )
        
        notch_point = point_on_circle(centre[0], centre[1], guage_radius, radians)
        
        self.display.set_pen(self.display.create_pen(0, 0, 0))
        self.circle(notch_point[0], notch_point[1], guage_thickness * 2)
        
        self.display.set_pen(self.display.create_pen(255, 255, 255))
        self.circle(notch_point[0], notch_point[1], guage_thickness)
        
        self.display.set_font("sans")
        self.draw_text(f"{current_temperature:.0f}", 1, position[0], position[1], size[0], size[1])
        
        self.display.set_font("bitmap8")
        text_y = int(position[1] + size[1] * 0.75)
        self.draw_text(f"{minimum_temperature:.0f}", 2, position[0], text_y, size[0] * 0.5, size[1] * 0.1)
        self.draw_text(f"{maximum_temperature:.0f}", 2, position[0] + size[0] * 0.5, text_y, size[0] * 0.5, size[1] * 0.1)

    def update(self):
        default_entity = dict(s = '0')
        minimum_temperature = float(self.entities.get(self.entity_ids['minimum_temp_entity_id'], default_entity)['s'])
        maximum_temperature = float(self.entities.get(self.entity_ids['maximum_temp_entity_id'], default_entity)['s'])
        current_temperature = float(self.entities.get(self.entity_ids['current_temp_entity_id'], default_entity)['s'])
        
        self.display.set_pen(self.display.create_pen(0, 0, 0))
        self.display.rectangle(self.display_width - 64, 0, 64, 70)
        
        self.draw_gauge((self.display_width - 64, 0), (64, 64), minimum_temperature, maximum_temperature, current_temperature)
        self.display.update()
