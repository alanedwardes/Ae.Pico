import asyncio
import utime
import chart
import colors

class RainDisplay:
    def __init__(self, display, hass, entity_id):
        self.display = display
        self.hass = hass
        self.entity_id = entity_id
        self.is_active = True
        
        self.display_width, self.display_height = self.display.get_bounds()
    
    CREATION_PRIORITY = 1
    def create(provider):
        config = provider['config']['rain']
        return RainDisplay(provider['display'], provider['hassws.HassWs'], config['entity_id'])
    
    def entity_updated(self, entity_id, entity):
        self.update()
    
    async def start(self):
        await self.hass.subscribe([self.entity_id], self.entity_updated)
        await asyncio.Event().wait()
        
    def should_activate(self):
        return True

    def activate(self, new_active):
        self.is_active = new_active
        if self.is_active:
            self.update()
       
    def draw_text(self, text, x, y, width, scale=1):
        text_width = self.display.measure_text(text, scale)
        text_height = scale * 8

        text_x = int(width * 0.5 - text_width * 0.5)
        
        half_height = text_height * 0.5
        
        self.display.text(text, int(text_x + x), int(y + half_height), scale=scale)
        
        return int(text_height)
        
    def update(self):
        if self.is_active == False:
            return
        
        start_update_ms = utime.ticks_ms()
        self.__update()
        update_time_ms = utime.ticks_diff(utime.ticks_ms(), start_update_ms)
        print(f"RainDisplay: {update_time_ms}ms")
    
    def __update(self):
        hours = self.hass.entities.get(self.entity_id, {}).get('a', {}).get('hours', [])
        
        if len(hours) == 0:
            return
        
        y_start = 70
               
        self.display.set_pen(self.display.create_pen(0, 0, 0))
        self.display.rectangle(0, y_start, self.display_width, self.display_height - y_start)

        self.display.set_pen(self.display.create_pen(64, 64, 64))
        self.display.rectangle(0, y_start + 35, self.display_width, 2)
        
        self.display.set_font('bitmap8')

        # generate random rain data for testing
        #import random
        #for i in range(len(hours)):
        #    hours[i]['r'] = random.randint(0, 100)

        column_width = self.display_width // (len(hours) - 1)
        for i, hour in enumerate(hours):
            if i == len(hours) - 1:
                continue

            hour_number = 12 if hour['h'] == 0 else hour['h']
            rain_chance = hour['r']
            temperature = hour['t']
            
            sx = i * column_width
            #sy = y_start + 10
            sy = y_start
            
            if i > 0:
                self.display.set_pen(self.display.create_pen(64, 64, 64))
                self.display.rectangle(sx, sy, 2, self.display_height - y_start)
            
            self.display.set_pen(self.display.create_pen(255, 255, 255))
            self.draw_text(f"{hour_number}", sx, sy, column_width, scale=2)
            
            sy += 35
            
            max_column_height = 70
            
            self.display.set_pen(self.display.create_pen(255, 255, 255))
            self.draw_text(f"{rain_chance}%", sx, sy + max_column_height + 5, column_width, scale=2)
            
            self.display.set_pen(self.display.create_pen(117, 150, 148))
            
            sy += max_column_height + 30
            
            self.display.set_pen(self.display.create_pen(*colors.get_color_for_temperature(temperature)))
            self.draw_text(f"{temperature:.0f}°", sx, sy, column_width, scale=2)

        chart_y = y_start + 45
        chart_height = 60

        self.display.set_pen(self.display.create_pen(64, 64, 64))
        self.display.rectangle(0, chart_y + chart_height, self.display_width, 2)

        polygon = []
        polygon.append((0, chart_y + chart_height))

        for px, py in chart.draw_chart(0, chart_y, self.display_width, chart_height, [hour['r'] / 100 for hour in hours], 32):
            polygon.append((int(px), int(py)))

        polygon.append((self.display_width, chart_y + chart_height))

        self.display.set_pen(self.display.create_pen(117, 150, 148))
        self.display.polygon(polygon)

        self.display.set_pen(self.display.create_pen(174, 220, 216))
        for px, py in chart.draw_chart(0, chart_y, self.display_width, chart_height, [hour['r'] / 100 for hour in hours]):
            self.display.circle(int(px), int(py), 2)

        self.display.update()
