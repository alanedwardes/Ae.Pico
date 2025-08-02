try:
    import ujson
except ModuleNotFoundError:
    import json as ujson

import asyncio
import utime
import colors
import struct
import re

URL_RE = re.compile(r'(http|https)://([A-Za-z0-9-\.]+)(?:\:([0-9]+))?(.+)?')

class WeatherDisplay:
    def __init__(self, display, url, rtc=None):
        self.display = display
        self.url = url
        self.rtc = rtc
        self.weather_data = []
        self.is_active = True
        
        self.display_width, self.display_height = self.display.get_bounds()
    
    CREATION_PRIORITY = 1
    def create(provider):
        rtc = provider.get('remotetime.RemoteTime')
        if not rtc:
            print('Falling back to machine.RTC as remotetime.Remotetime unavailable')
            import machine
            rtc = machine.RTC()
        return WeatherDisplay(provider['display'], provider['config']['weather']['url'], rtc)
    
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
            if self.rtc:
                now = self.rtc.datetime()
                # Calculate day of week (0 = Monday)
                day_of_week = (now[6] + 6) % 7  # Convert from MicroPython RTC format
            else:
                day_of_week = i  # Fallback to just using index
            
            if day_of_week == 5 or day_of_week == 6:  # Saturday or Sunday
                self.display.set_pen(self.display.create_pen(201, 205, 209))
            else:
                self.display.set_pen(self.display.create_pen(255, 255, 255))
            
            self.draw_text(f"{day_names[day_of_week]}", sx, sy, column_width, scale=2)
            
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