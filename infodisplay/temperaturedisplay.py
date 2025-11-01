import gauge
import textbox
import math
import utime
import asyncio

class TemperatureDisplay:
    def __init__(self, display, hass, entity_ids):
        self.display = display
        self.hass = hass
        self.entity_ids = entity_ids

        self.display_width, self.display_height = self.display.get_bounds()
        
        self.alpha = 0
    
    CREATION_PRIORITY = 1
    def create(provider):
        return TemperatureDisplay(provider['display'], provider['hassws.HassWs'], provider['config']['temperature'])
    
    def entity_updated(self, entity_id, entity):
        self.update()
    
    async def start(self):
        await self.hass.subscribe(self.entity_ids.values(), self.entity_updated)
        # For testing
        #while True:
        #    self.update()
        #    await asyncio.sleep(1)
        await asyncio.Event().wait()
        
    def update(self):
        start_update_ms = utime.ticks_ms()
        self.__update()
        update_time_ms = utime.ticks_diff(utime.ticks_ms(), start_update_ms)
        print(f"TemperatureDisplay: {update_time_ms}ms")

    def __update(self):
        default_entity = dict(s = '0')
        minimum_temperature = float(self.hass.entities.get(self.entity_ids['minimum_temp_entity_id'], default_entity)['s'])
        maximum_temperature = float(self.hass.entities.get(self.entity_ids['maximum_temp_entity_id'], default_entity)['s'])
        current_temperature = float(self.hass.entities.get(self.entity_ids['current_temp_entity_id'], default_entity)['s'])
        
        self.display.rect(self.display_width - 64, 0, 64, 70, 0x0000, True)
        
        position = (self.display_width - 64, 0)
        size = (64, 64)
        gauge.draw_gauge(self.display, position, size, minimum_temperature, maximum_temperature, current_temperature)
        
        # Draw current temperature in the gauge
        white_pen = 0xFFFF
        primary_scale = size[1] * 0.06
        primary_height = size[1]
        textbox.draw_textbox(self.display, f'{current_temperature:.0f}', position[0], position[1], size[0], primary_height, color=white_pen, font='notosans')
        
        # Draw min/max labels under the gauge
        centre_x = size[0] / 2 + position[0]
        centre_y = size[1] / 2 + position[1]
        extent_left = centre_x - size[1] * 0.5
        text_y = int(position[1] + size[1] * 0.75)
        text_size_x = size[1] * 0.5
        text_scale = max(1, math.ceil(size[1] * 0.02))
        text_height = 8 * text_scale
        text_size_y = text_height + 4
        textbox.draw_textbox(self.display, f'{minimum_temperature:.0f}', extent_left, text_y, text_size_x, text_size_y, color=white_pen, font='notosanssmall')
        textbox.draw_textbox(self.display, f'{maximum_temperature:.0f}', centre_x, text_y, text_size_x, text_size_y, color=white_pen, font='notosanssmall')
        self.display.update()
