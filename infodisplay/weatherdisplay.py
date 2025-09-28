try:
    import ujson
except ModuleNotFoundError:
    import json as ujson

import asyncio
import utime
import colors
import struct
import re
import textbox

URL_RE = re.compile(r'(http|https)://([A-Za-z0-9-\.]+)(?:\:([0-9]+))?(.+)?')

class WeatherDisplay:
    def __init__(self, display, url, rtc=None):
        self.display = display
        self.url = url
        self.weather_data = []
        self.is_active = True
        
        self.display_width, self.display_height = self.display.get_bounds()
    
    CREATION_PRIORITY = 1
    def create(provider):
        return WeatherDisplay(provider['display'], provider['config']['weather']['url'])
    
    def entity_updated(self, entity_id, entity):
        pass  # No longer using Home Assistant entities
    
    async def start(self):
        while True:
            await self.fetch_weather_data()
            self.update()
            await asyncio.sleep(300)
        
    def should_activate(self):
        return True

    def activate(self, new_active):
        self.is_active = new_active
        if self.is_active:
            self.update()
    
    def parse_url(self, url):
        match = URL_RE.match(url)
        if match:
            protocol = match.group(1)
            host = match.group(2)
            port = match.group(3)
            path = match.group(4)

            if protocol == 'https':
                if port is None:
                    port = 443
            elif protocol == 'http':
                if port is None:
                    port = 80
            else:
                raise ValueError('Scheme {} is invalid'.format(protocol))

            return (host, int(port), path if path else '/', protocol == 'https')
        raise ValueError('Invalid URL format')
    
    async def fetch_weather_data(self):
        try:               
            url = self.url
            host, port, path, use_ssl = self.parse_url(url)
            
            reader, writer = await asyncio.open_connection(host, port, ssl=use_ssl)
            
            # Write HTTP request
            writer.write(f'GET {path} HTTP/1.0\r\n'.encode('utf-8'))
            writer.write(f'Host: {host}\r\n'.encode('utf-8'))
            writer.write(b'\r\n')
            await writer.drain()
            
            # Read response
            line = await reader.readline()
            status = line.split(b' ', 2)
            status_code = int(status[1])
            
            if status_code != 200:
                print(f"Failed to fetch weather data: {status_code}")
                writer.close()
                await writer.wait_closed()
                return
            
            # Skip headers
            while True:
                line = await reader.readline()
                if line == b'\r\n':
                    break
            
            # Read content
            content = await reader.read()
            writer.close()
            await writer.wait_closed()
            
            self.weather_data = ujson.loads(content.decode('utf-8'))
            print(f"Weather data fetched: {len(self.weather_data)} data points")
            for i in range(0, len(self.weather_data), 3):
                if i + 2 < len(self.weather_data):
                    code = self.weather_data[i]
                    temp = self.weather_data[i + 1]
                    rain = self.weather_data[i + 2]
                    print(f"  Day {i//3}: Code {code}, Temp {temp}°C, Rain {rain}%")
                
        except Exception as e:
            print(f"Error fetching weather data: {e}")
    
    def draw_icon(self, icon_name, framebuffer, x, y, box_width, box_height):
        try:
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
        except OSError as e:
            print(f"Warning: Could not load icon '{icon_name}': {e}")
            return
    
        
    def update(self):
        if self.is_active == False:
            return
        
        start_update_ms = utime.ticks_ms()
        self.__update()
        update_time_ms = utime.ticks_diff(utime.ticks_ms(), start_update_ms)
        print(f"WeatherDisplay: {update_time_ms}ms")
    
    def __update(self):
        if len(self.weather_data) == 0:
            return
        
        y_start = 70
        
        palette = []        
        self.display.set_pen(self.display.create_pen(255, 255, 255))
        self.display.set_pen(self.display.create_pen(0, 0, 0))
        self.display.set_pen(self.display.create_pen(242, 106, 48))
        
        self.display.set_pen(self.display.create_pen(0, 0, 0))
        self.display.rectangle(0, y_start, self.display_width, self.display_height - y_start)
        
        day_names = ['MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT', 'SUN']
        
        # Calculate number of days from data (each day has 3 values: code, temp, rain)
        num_days = len(self.weather_data) // 3
        column_width = self.display_width // num_days
        
        for i in range(num_days):
            data_index = i * 3
            if data_index + 2 >= len(self.weather_data):
                break
                
            weather_code = self.weather_data[data_index]
            temperature = self.weather_data[data_index + 1]
            rain = self.weather_data[data_index + 2]
            
            sx = i * column_width
            sy = y_start + 10
            
            # Get current day of week (0 = Monday, 6 = Sunday)
            # Use utime to get current time and calculate day of week
            now = utime.localtime()
            # Calculate day of week (0 = Monday) and increment for each column
            day_of_week = (now[6] + i) % 7  # MicroPython already uses 0=Monday, so no conversion needed
            
            if day_of_week == 5 or day_of_week == 6:  # Saturday or Sunday
                self.display.set_pen(self.display.create_pen(201, 205, 209))
            else:
                self.display.set_pen(self.display.create_pen(255, 255, 255))
            
            height = 2 * 8
            textbox.draw_textbox(self.display, f"{day_names[day_of_week]}", sx, sy, column_width, height, font='bitmap8', scale=2)
            
            sy += 25
            
            icon = self.draw_icon(weather_code, memoryview(self.display), sx, sy, column_width, 50)
            self.display.set_pen(self.display.create_pen(255, 255, 255))
            
            sy += 50

            self.display.set_pen(self.display.create_pen(*colors.get_color_for_temperature(temperature)))
            height = 2 * 8
            textbox.draw_textbox(self.display, f"{temperature:.0f}°", sx, sy, column_width, height, font='bitmap8', scale=2)
            
            sy += 30
            
            rain_color = colors.get_color_for_rain_percentage(rain)
            self.display.set_pen(self.display.create_pen(rain_color[0], rain_color[1], rain_color[2]))
            
            height = 2 * 8
            textbox.draw_textbox(self.display, f"{rain}%", sx, sy, column_width, height, font='bitmap8', scale=2)

        self.display.update()