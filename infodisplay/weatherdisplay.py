import asyncio
import utime
import colors
import struct

class WeatherDisplay:
    def __init__(self, display, hass, entity_id):
        self.display = display
        self.hass = hass
        self.entity_id = entity_id
        self.is_active = True
        
        self.display_width, self.display_height = self.display.get_bounds()
    
    CREATION_PRIORITY = 1
    def create(provider):
        config = provider['config']['weather']
        return WeatherDisplay(provider['display'], provider['hassws.HassWs'], config['entity_id'])
    
    def entity_updated(self, entity_id, entity):
        self.update()
    
    async def start(self):
        await self.hass.subscribe([self.entity_id], self.entity_updated)
        # For testing
        #while True:
        #    self.update()
        #    await asyncio.sleep(1)
        await asyncio.Event().wait()
        
    def should_activate(self):
        return True

    def activate(self, new_active):
        self.is_active = new_active
        if self.is_active:
            self.update()
    
    def draw_icon(self, icon_name, framebuffer, x, y, box_width, box_height):
        with open(f'icons/{icon_name}.bin', 'rb') as icon_file:
            icon_width, icon_height = struct.unpack('<HH', icon_file.read(4))
            # Center the icon in the given box
            icon_x = x + (box_width - icon_width) // 2
            icon_y = y + (box_height - icon_height) // 2

            # Calculate bytes per pixel from framebuffer size and display dimensions
            total_pixels = self.display_width * self.display_height
            bytes_per_pixel = len(framebuffer) // total_pixels

            icon_row_bytes = icon_width * bytes_per_pixel
            fb_row_bytes = self.display_width * bytes_per_pixel

            for row in range(icon_height):
                fb_y = row + icon_y
                if 0 <= fb_y < self.display_height:
                    fb_start = fb_y * fb_row_bytes + icon_x * bytes_per_pixel
                    mv = memoryview(framebuffer)[fb_start : fb_start + icon_row_bytes]
                    icon_file.readinto(mv)
                else:
                    icon_file.seek(icon_row_bytes, 1)
    
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
        print(f"WeatherDisplay: {update_time_ms}ms")
    
    def __update(self):
        days = self.hass.entities.get(self.entity_id, {}).get('a', {}).get('days', [])
        
        if len(days) == 0:
            return
        
        y_start = 70
        
        palette = []        
        self.display.set_pen(self.display.create_pen(255, 255, 255))
        self.display.set_pen(self.display.create_pen(0, 0, 0))
        self.display.set_pen(self.display.create_pen(242, 106, 48))
        
        self.display.set_pen(self.display.create_pen(0, 0, 0))
        self.display.rectangle(0, y_start, self.display_width, self.display_height - y_start)
        
        day_names = ['MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT', 'SUN']
        
        met_office_codes = {
            "NA": "not-available",
            -1: "raindrop",  # Trace rain
            0: "clear-night",
            1: "clear-day",  # sunny day
            2: "partly-cloudy-night",
            3: "partly-cloudy-day",
            4: "not-available",  # Not used
            5: "mist",
            6: "fog",
            7: "cloudy",
            8: "overcast",
            9: "partly-cloudy-night-rain",  # Light rain shower (night)
            10: "partly-cloudy-day-rain",   # Light rain shower (day)
            11: "drizzle",
            12: "rain",  # Light rain
            13: "partly-cloudy-night-rain",  # Heavy rain shower (night)
            14: "partly-cloudy-day-rain",    # Heavy rain shower (day)
            15: "rain",  # Heavy rain
            16: "partly-cloudy-night-sleet",  # Sleet shower (night)
            17: "partly-cloudy-day-sleet",    # Sleet shower (day)
            18: "sleet",
            19: "partly-cloudy-night-hail",   # Hail shower (night)
            20: "partly-cloudy-day-hail",     # Hail shower (day)
            21: "hail",
            22: "partly-cloudy-night-snow",   # Light snow shower (night)
            23: "partly-cloudy-day-snow",     # Light snow shower (day)
            24: "snow",  # Light snow
            25: "partly-cloudy-night-snow",   # Heavy snow shower (night)
            26: "partly-cloudy-day-snow",     # Heavy snow shower (day)
            27: "snow",  # Heavy snow
            28: "thunderstorms-night",        # Thunder shower (night)
            29: "thunderstorms-day",          # Thunder shower (day)
            30: "thunderstorms",              # Thunder
        }
        
        self.display.set_font('bitmap8')
        
        column_width = self.display_width // len(days)
        for i, day in enumerate(days):
            day_number = day['d']
            weather_code = day['c']
            temperature = day['t']
            rain = day['r']
            
            sx = i * column_width
            sy = y_start + 10
            
            if day_number == 5 or day_number == 6:
                self.display.set_pen(self.display.create_pen(201, 205, 209))
            else:
                self.display.set_pen(self.display.create_pen(255, 255, 255))
            
            self.draw_text(f"{day_names[day_number]}", sx, sy, column_width, scale=2)
            
            sy += 25
            
            icon = self.draw_icon(met_office_codes[weather_code], memoryview(self.display), sx, sy, column_width, 50)
            self.display.set_pen(self.display.create_pen(255, 255, 255))
            
            sy += 50

            self.display.set_pen(self.display.create_pen(*colors.get_color_for_temperature(temperature)))
            self.draw_text(f"{temperature:.0f}°", sx, sy, column_width, scale=2)
            
            sy += 30
            
            if rain > 50:
                self.display.set_pen(self.display.create_pen(174, 220, 216))
            else:
                self.display.set_pen(self.display.create_pen(137, 142, 149))
            
            self.draw_text(f"{rain}%", sx, sy, column_width, scale=2)

        self.display.update()