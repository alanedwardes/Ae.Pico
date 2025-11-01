import utime
import colors
import asyncio
import textbox

class InfoDisplay:
    def __init__(self, display, middle_row, bottom_row, hass):
        self.display = display
        self.hass = hass
        self.is_active = True

        self.display_width, self.display_height = self.display.get_bounds()
        self.display_half_width = self.display_width * 0.5
        
        self.middle_row = middle_row
        self.bottom_row = bottom_row
    

    def draw_rectangle(self, width, height, y, color):
        x = int(self.display_half_width - width * 0.5)
        self.display.rect(x, y, width, height, color, True)
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
                return colors.get_color_for_temperature(float(value))
            except:
                pass
            
        if subscription.get('uv', False):
            try:
                return colors.get_color_for_uv(int(value))
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
        start_update_ms = utime.ticks_ms()
        self.__update()
        update_time_ms = utime.ticks_diff(utime.ticks_ms(), start_update_ms)
        print(f"InfoDisplay: {update_time_ms}ms")

    def __update(self):
        self.white = 0xFFFF
        self.black = 0x0000
        self.grey = 0x8410
        
        y = 70
        
        self.display.rect(0, y, self.display_width, self.display_height - y, self.black, True)

        #spacer = 10
        
        x = 0
        middle_row_item_width = len(self.middle_row) and self.display_width / len(self.middle_row) or 0
        for i, subscription in enumerate(self.middle_row):
            value = self._get_entity_value(subscription)
            value_color = self._get_pen_color(subscription, value)
            if i == 0:
                y += self.draw_rectangle(320, 8, y, value_color)
            
            top_height = 1.5 * 30
            textbox.draw_textbox(self.display, self._format_entity_value(subscription, value), x, y, middle_row_item_width, top_height, color=value_color, font='sans', scale=1.5)
            label_height = 1 * 25
            textbox.draw_textbox(self.display, subscription.get('label', '?'), x, y + top_height, middle_row_item_width, label_height, color=self.grey, font='sans', scale=1)
            x += middle_row_item_width
        
        x = 0
        y += 75
            
        bottom_row_item_width = len(self.bottom_row) and self.display_width / len(self.bottom_row) or 0
        for i, subscription in enumerate(self.bottom_row):
            value = self._get_entity_value(subscription)
            value_color = self._get_pen_color(subscription, value)
            if i == 0:
                y += self.draw_rectangle(320, 8, y, value_color)
            
            top_height = 1.5 * 30
            textbox.draw_textbox(self.display, self._format_entity_value(subscription, value), x, y, bottom_row_item_width, top_height, color=value_color, font='sans', scale=1.5)
            label_height = 1 * 25
            textbox.draw_textbox(self.display, subscription.get('label', '?'), x, y + top_height, bottom_row_item_width, label_height, color=self.grey, font='sans', scale=1)
            x += bottom_row_item_width
        
        self.display.update()