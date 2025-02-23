import utime
import asyncio

class InfoDisplay:
    MONTHS = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC']
    DAYS = ['MO', 'TU', 'WE', 'TH', 'FR', 'SA', 'SU']
    
    def __init__(self, display, middle_row, bottom_row, nic, hass, rtc):
        self.display = display
        self.wlan = nic
        self.hass = hass
        self.rtc = rtc
        
        self.white = self.display.create_pen(255, 255, 255)
        self.grey = self.display.create_pen(128, 128, 128)
        self.black = self.display.create_pen(0, 0, 0)
        
        self.over_41c = self.display.create_pen(154, 27, 30)
        self.over_30c = self.display.create_pen(238, 45, 41)
        self.over_21c = self.display.create_pen(242, 106, 48)
        self.over_17c = self.display.create_pen(250, 163, 26)
        self.over_15c = self.display.create_pen(251, 182, 22)
        self.over_11c = self.display.create_pen(254, 219, 0)
        self.over_9c = self.display.create_pen(208, 215, 62)
        self.over_7c = self.display.create_pen(175, 210, 81)
        self.over_5c = self.display.create_pen(159, 205, 128)
        self.over_3c = self.display.create_pen(170, 214, 174)
        self.over_1c = self.display.create_pen(174, 220, 216)
        self.over_n10 = self.display.create_pen(55, 137, 198)
        self.cold = self.display.create_pen(2, 98, 169)
        
        self.red = self.over_21c

        self.display_width, self.display_height = self.display.get_bounds()
        self.display_half_width = self.display_width * 0.5
        
        self.entities = {}
        self.middle_row = middle_row
        self.bottom_row = bottom_row
        
        self.last_update_time_ms = 0
    
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
        return self.white
    
    CREATION_PRIORITY = 1
    def create(provider):
        config = provider['config']['display']
        rtc = provider.get('remotetime.RemoteTime')
        if not rtc:
            print('Falling back to machine.RTC as remotetime.Remotetime unavailable')
            import machine
            rtc = machine.RTC()
        return InfoDisplay(provider['display'], config.get('middle_row', []), config.get('bottom_row', []), provider['nic'], provider['hassws.HassWs'], rtc)
    
    def entity_updated(self, entity_id, entity):
        self.entities[entity_id] = entity
        self.update()
    
    async def start(self):
        await self.hass.subscribe([item['entity_id'] for item in self.middle_row + self.bottom_row], self.entity_updated)
        
        while True:
            self.update()
            # Assume subseconds component of RTC means milliseconds
            await asyncio.sleep_ms(max(min(1000 - self.rtc.datetime()[7], 1000), 0))

    def update(self):
        start_update_ms = utime.ticks_ms()
        self.__update()
        self.last_update_time_ms = utime.ticks_diff(utime.ticks_ms(), start_update_ms)

    def __update(self):
        self.display.set_font("sans")
        self.display.set_pen(self.black)
        self.display.clear()

        now = self.rtc.datetime()
        
        spacer = 16
        
        y = spacer
        
        self.display.set_pen(self.white)
        
        screen_width_third = self.display_width / 5
        
        seconds_width = screen_width_third * 1
        time_width = screen_width_third * 3
        
        # Hours and minutes
        y += self.draw_text("%02i:%02i" % (now[4], now[5]), 2.25, 4, y, time_width)
        
        # Seconds and day
        self.draw_text("%s" % self.DAYS[now[3]-1], 1, time_width, 10, seconds_width)
        self.draw_text("%02i" % now[6], 1.2, time_width, 40, seconds_width)
        
        calendar_outline_x = int(time_width + seconds_width)
        calendar_outline_y = 0
        calendar_outline_w = int(seconds_width)
        calendar_outline_h = y + spacer
        
        # Calendar outline
        self.display.set_pen(self.red)
        self.display.rectangle(calendar_outline_x, calendar_outline_y, calendar_outline_w, calendar_outline_h)
        
        date_outline_x = calendar_outline_x
        date_outline_y = 36
        date_outline_w = calendar_outline_w
        date_outline_h = 36
        
        # Date outline
        self.display.set_pen(self.white)
        self.display.rectangle(date_outline_x, date_outline_y, date_outline_w, date_outline_h)
        
        # Date and month
        self.draw_text("%s" % self.MONTHS[now[1]-1], 1, time_width + seconds_width, 10, seconds_width)
        self.display.set_pen(self.black)
        self.draw_text("%02i" % now[2], 1.2, date_outline_x, date_outline_y + 8, date_outline_w)
        
        y += spacer
        
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

        self.display.set_font("bitmap8")
        self.display.set_pen(self.grey)
        self.display.set_thickness(1)
        self.display.text("%idB %ims" % (self.wlan.status('rssi'), self.last_update_time_ms), 0, 240, scale=1, angle=270)
        
        self.display.update()
