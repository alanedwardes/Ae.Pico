import utime
import colors
import asyncio

class InfoDisplay:
    def __init__(self, display, middle_row, bottom_row, hass):
        self.display = display
        self.hass = hass
        self.is_active = True

        self.display_width, self.display_height = self.display.get_bounds()
        self.display_half_width = self.display_width * 0.5
        
        self.middle_row = middle_row
        self.bottom_row = bottom_row
    
    def draw_text(self, text, scale, x, y, width):
        text_width = self.display.measure_text(text, scale)
        text_height = scale * 20
        self.display.set_thickness(int(scale * 3))

        text_x = int(width * 0.5 - text_width * 0.5)
        
        half_height = text_height * 0.5
        
        self.display.text(text, int(text_x + x), int(y + half_height), scale=scale)
        
        return int(text_height)

    def draw_rectangle(self, width, height, y):
        x = int(self.display_half_width - width * 0.5)        
        self.display.rectangle(x, y, width, height)        
        return height
    
    def _get_entity_value(self, subscription):
        entity = self.hass.entities.get(subscription['entity_id'], {})
        
        value = None
        attribute_name = subscription.get('attribute', None)
        if attribute_name is not None:
            return entity.get('a', {}).get(attribute_name, None)
        else:
            return entity.get('s', None)
        
    def _format_entity_value(self, subscription, value):
        try:
            return subscription['format'](value)
        except:
            return '?'
        
    def _get_pen_color(self, subscription, value):
        if subscription.get('temperature', False):
            try:
                return self.display.create_pen(*colors.get_color_for_temperature(float(value)))
            except:
                pass
            
        if subscription.get('uv', False):
            try:
                return self.display.create_pen(*colors.get_color_for_uv(int(value)))
            except:
                pass
        
        return self.white
    
    CREATION_PRIORITY = 1
    def create(provider):
        config = provider['config']['info']
        return InfoDisplay(provider['display'], config.get('middle_row', []), config.get('bottom_row', []), provider['hassws.HassWs'])
    
    def entity_updated(self, entity_id, entity):
        self.update()
    
    async def start(self):
        await self.hass.subscribe([item['entity_id'] for item in self.middle_row + self.bottom_row], self.entity_updated)
        await asyncio.Event().wait()
        
    def should_activate(self):
        return True

    def activate(self, new_active):
        self.is_active = new_active
        if self.is_active:
            self.update()

    def update(self):
        if self.is_active == False:
            return
        
        self.__update()

    def __update(self):
        self.white = self.display.create_pen(255, 255, 255)
        self.black = self.display.create_pen(0, 0, 0)
        self.grey = self.display.create_pen(128, 128, 128)
        
        y = 70
        
        self.display.set_font("sans")
        self.display.set_pen(self.black)
        self.display.rectangle(0, y, self.display_width, self.display_height - y)

        spacer = 16
        
        x = 0
        middle_row_item_width = len(self.middle_row) and self.display_width / len(self.middle_row) or 0
        for i, subscription in enumerate(self.middle_row):
            value = self._get_entity_value(subscription)
            self.display.set_pen(self._get_pen_color(subscription, value))
            if i == 0:
                y += self.draw_rectangle(320, 8, y) + spacer
            
            top_text_height = self.draw_text(self._format_entity_value(subscription, value), 1.5, x, y, middle_row_item_width)
            self.display.set_pen(self.grey)
            self.draw_text(subscription.get('label', '?'), 1, x, y + top_text_height, middle_row_item_width)
            x += middle_row_item_width
        
        x = 0
        y += 60
            
        bottom_row_item_width = len(self.bottom_row) and self.display_width / len(self.bottom_row) or 0
        for i, subscription in enumerate(self.bottom_row):
            value = self._get_entity_value(subscription)
            self.display.set_pen(self._get_pen_color(subscription, value))
            if i == 0:
                y += self.draw_rectangle(320, 8, y) + spacer
            
            top_text_height = self.draw_text(self._format_entity_value(subscription, value), 1.5, x, y, bottom_row_item_width)
            self.display.set_pen(self.grey)
            self.draw_text(subscription.get('label', '?'), 1, x, y + top_text_height, bottom_row_item_width)
            x += bottom_row_item_width
        
        self.display.update()