import asyncio
import bitmap
import utime

class WeatherDisplay:
    def __init__(self, display, hass, entity_id):
        self.display = display
        self.hass = hass
        self.entity_id = entity_id
        self.days = []
        self.is_active = True
        
        self.display_width, self.display_height = self.display.get_bounds()
    
    CREATION_PRIORITY = 1
    def create(provider):
        config = provider['config']['weather']
        return WeatherDisplay(provider['display'], provider['hassws.HassWs'], config['entity_id'])
    
    def entity_updated(self, entity_id, entity):
        self.days = entity['a']['days']
        self.update()
    
    async def start(self):
        await self.hass.subscribe([self.entity_id], self.entity_updated)
        self.bitmap = open('weather_icons.bmp', 'rb')
        self.bitmap_header = bitmap.read_header(self.bitmap)
        while True:
            self.update()
            await asyncio.sleep(1)
        await asyncio.Event().wait()
        
    def should_activate(self):
        return True

    def activate(self, new_active):
        self.is_active = new_active
        if self.is_active:
            self.update()
            
    def read_icon(self, palette, offset_x, offset_y, start_row, total_rows, scale):
        for y, row in enumerate(bitmap.read_pixels(self.bitmap, self.bitmap_header, start_row)):
            if y > total_rows:
                return
            
            last_pen = None
            for x, color in enumerate(row):
                if color == (0, 0, 0):
                    continue
                
                if last_pen != color:
                    self.display.set_pen_color(color, palette)
                    
                #self.display.rectangle(offset_x + (x * scale), offset_y + (y * scale), scale, scale)                
                self.display.pixel(offset_x + x, offset_y + y)
                last_pen = color
    
    def draw_icon(self, icon, palette, offset_x, offset_y, width, height):
        icons = {
            'sun': (0, 36),
            'wind': (36, 23),
            'partial': (60, 24),
            'fog': (84, 31),
            'rain': (116, 30),
            'cloud': (146, 21),
            'lightning': (168, 31)
        }
        offset = icons[icon]
        icon_height = offset[1]
        icon_width = 39
             
        centered_offset_x = offset_x + (width - icon_width) // 2
        centered_offset_y = offset_y + (height - icon_height) // 2
        
        self.read_icon(palette, centered_offset_x, centered_offset_y, offset[0], offset[1], 1)
    
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
        print(update_time_ms)
    
    def __update(self):
        if len(self.days) == 0:
            return
        
        y_start = 70
        
        palette = [(255, 255, 255), (0, 0, 0), (242, 106, 48)]
        
        self.display.set_pen_color((0, 0, 0), palette)
        self.display.rectangle(0, y_start, self.display_width, self.display_height - y_start)
        
        day_names = ['MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT', 'SUN']
        
        met_office_codes = {
            -1: 'rain',
            0: 'sun',
            1: 'sun',
            2: 'partial',
            3: 'partial',
            5: 'fog',
            6: 'fog',
            7: 'cloud',
            8: 'partial',
            9: 'rain',
            10: 'rain',
            11: 'rain',
            12: 'rain',
            13: 'rain',
            14: 'rain',
            15: 'rain',
            16: 'rain',
            17: 'rain',
            18: 'rain',
            19: 'rain',
            20: 'rain',
            21: 'rain',
            22: 'rain',
            23: 'rain',
            24: 'rain',
            25: 'rain',
            26: 'rain',
            27: 'rain',
            28: 'lightning',
            29: 'lightning',
            30: 'lightning'
        }
        
        self.display.set_font('bitmap8')
        
        column_width = self.display_width // len(self.days)
        for i, day in enumerate(self.days):
            day_number = day['d']
            weather_code = day['c']
            temperature = day['t']
            rain = day['r']
            
            sx = i * column_width
            sy = y_start + 10
            
            if day_number == 5 or day_number == 6:
                self.display.set_pen_color((201, 205, 209), palette)
            else:
                self.display.set_pen_color((255, 255, 255), palette)
            
            self.draw_text(f"{day_names[day_number]}", sx, sy, column_width, scale=2)
            
            sy += 25
            
            icon = self.draw_icon(met_office_codes[weather_code], palette, sx, sy, column_width, 50)
            self.display.set_pen_color((255, 255, 255), palette)
            
            sy += 50
            
            if temperature > 21:
                self.display.set_pen_color((242, 106, 48), palette)
            elif temperature > 15:
                self.display.set_pen_color((251, 182, 22), palette)
            elif temperature > 11:
                self.display.set_pen_color((254, 219, 0), palette)
            elif temperature > 5:
                self.display.set_pen_color((159, 205, 128), palette)
            else:
                self.display.set_pen_color((174, 220, 216), palette)
            
            self.draw_text(f"{temperature:.0f}°", sx, sy, column_width, scale=2)
            
            sy += 30
            
            if rain > 50:
                self.display.set_pen_color((174, 220, 216), palette)
            elif rain > 5:
                self.display.set_pen_color((137, 142, 149), palette)
            else:
                continue
            
            self.draw_text(f"{rain}%", sx, sy, column_width, scale=2)

        self.display.update()
