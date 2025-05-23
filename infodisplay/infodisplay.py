import asyncio

class InfoDisplay:
    def __init__(self, display, middle_row, bottom_row, hass):
        self.display = display
        self.hass = hass
        self.is_active = True
        
        self.white = 0
        self.black = 1
        self.red = 2
        
        self.grey = 3
        self.over_41c = 4
        self.over_30c = 5
        self.over_21c = self.red
        self.over_17c = 6
        self.over_15c = 7
        self.over_11c = 8
        self.over_9c = 9
        self.over_7c = 10
        self.over_5c = 11
        self.over_3c = 12
        self.over_1c = 13
        self.over_n10 = 14
        self.cold = 15

        self.display_width, self.display_height = self.display.get_bounds()
        self.display_half_width = self.display_width * 0.5
        
        self.entities = {}
        self.middle_row = middle_row
        self.bottom_row = bottom_row
    
    def pen_for_temp(self, temp):
        if temp >= 41:
            return self.over_41c
        elif temp >= 30:
            return self.over_30c
        elif temp >= 21:
            return self.over_21c
        elif temp >= 17:
            return self.over_17c
        elif temp >= 15:
            return self.over_15c
        elif temp >= 11:
            return self.over_11c
        elif temp >= 9:
            return self.over_9c
        elif temp >= 7:
            return self.over_7c
        elif temp >= 5:
            return self.over_5c
        elif temp >= 3:
            return self.over_3c
        elif temp >= 1:
            return self.over_1c
        elif temp >= -10:
            return self.over_n10
        else:
            return self.cold
        
    def pen_for_uv(self, uv):
        if uv < 3:
            return self.over_5c
        elif uv < 5:
            return self.over_11c
        elif uv < 7:
            return self.over_21c
        elif uv < 10:
            return self.over_30c
        else:
            return self.cold
    
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
        entity = self.entities.get(subscription['entity_id'], {})
        
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
                return self.pen_for_temp(float(value))
            except:
                pass
            
        if subscription.get('uv', False):
            try:
                return self.pen_for_uv(int(value))
            except:
                pass
        
        return self.white
    
    CREATION_PRIORITY = 1
    def create(provider):
        config = provider['config']['info']
        return InfoDisplay(provider['display'], config.get('middle_row', []), config.get('bottom_row', []), provider['hassws.HassWs'])
    
    def entity_updated(self, entity_id, entity):
        self.entities[entity_id] = entity
        self.update()
    
    async def start(self):
        await self.hass.subscribe([item['entity_id'] for item in self.middle_row + self.bottom_row], self.entity_updated)
        await asyncio.Event().wait()

    def activate(self, new_active):
        self.is_active = new_active
        if self.is_active:
            self.update()

    def update(self):
        if self.is_active == False:
            return
        
        self.__update()

    def __update(self):
        self.display.update_pen(self.white, 255, 255, 255)
        self.display.update_pen(self.grey, 128, 128, 128)
        self.display.update_pen(self.black, 0, 0, 0)
        self.display.update_pen(self.over_41c, 154, 27, 30)
        self.display.update_pen(self.over_30c, 238, 45, 41)
        self.display.update_pen(self.over_21c, 242, 106, 48)
        self.display.update_pen(self.over_17c, 250, 163, 26)
        self.display.update_pen(self.over_15c, 251, 182, 22)
        self.display.update_pen(self.over_11c, 254, 219, 0)
        self.display.update_pen(self.over_9c, 208, 215, 62)
        self.display.update_pen(self.over_7c, 175, 210, 81)
        self.display.update_pen(self.over_5c, 159, 205, 128)
        self.display.update_pen(self.over_3c, 170, 214, 174)
        self.display.update_pen(self.over_1c, 174, 220, 216)
        self.display.update_pen(self.over_n10, 55, 137, 198)
        self.display.update_pen(self.cold, 2, 98, 169)
        
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