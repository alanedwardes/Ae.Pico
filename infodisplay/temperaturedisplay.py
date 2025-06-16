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

    def update(self):
        default_entity = dict(s = '0')
        minimum_temperature = float(self.entities.get(self.entity_ids['minimum_temp_entity_id'], default_entity)['s'])
        maximum_temperature = float(self.entities.get(self.entity_ids['maximum_temp_entity_id'], default_entity)['s'])
        current_temperature = float(self.entities.get(self.entity_ids['current_temp_entity_id'], default_entity)['s'])
        
        start_x = self.display_width - 64
        
        width = 64
        
        height = 70
        
        self.display.set_font("sans")
        self.display.set_pen(self.display.create_pen(0, 0, 0))
        self.display.rectangle(start_x, 0, width, height)
        
        self.display.set_pen(self.display.create_pen(255, 255, 255))
        
        circle_center_x = start_x + int(width / 2.0)
        circle_center_y = 30
        
        self.display.set_pen(self.display.create_pen(255, 255, 255))
        self.display.circle(circle_center_x, circle_center_y, 30)
        
        self.display.set_pen(self.display.create_pen(0, 0, 0))        
        self.display.circle(circle_center_x, circle_center_y, 25)
        
        self.display.triangle(start_x, 50, start_x + int(width / 2.0), int(height / 2.0), self.display_width, 50)
        self.display.rectangle(start_x, 50, width, 20)
        
        guage_min_max_radians = (2.6, 6.8)        
        radians = get_mapped_range_value_clamped((minimum_temperature, maximum_temperature), guage_min_max_radians, current_temperature)
        
        guage_radius = 27.5        
        px = circle_center_x + guage_radius * math.cos(radians);
        py = circle_center_y + guage_radius * math.sin(radians);
        self.display.circle(int(px), int(py), 6)
        
        self.display.set_pen(self.display.create_pen(255, 255, 255))
        
        self.display.circle(int(px), int(py), 3)
        self.draw_text(f"{current_temperature:.0f}", 1, start_x, 12, width, int(height / 2.0))
        
        self.display.set_font("bitmap8")
        self.display.text(f"{minimum_temperature:.0f}", start_x + 10, 52, scale=2)
        self.display.text(f"{maximum_temperature:.0f}", start_x + 40, 52, scale=2)
        
        self.display.update()
