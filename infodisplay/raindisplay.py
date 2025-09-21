try:
    import ujson
except ModuleNotFoundError:
    import json as ujson

import asyncio
import utime
import chart
import colors
import re
import textbox

URL_RE = re.compile(r'(http|https)://([A-Za-z0-9-\.]+)(?:\:([0-9]+))?(.+)?')

class RainDisplay:
    def __init__(self, display, url, rtc=None):
        self.display = display
        self.url = url
        self.weather_data = []
        self.is_active = True
        
        self.display_width, self.display_height = self.display.get_bounds()
    
    CREATION_PRIORITY = 1
    def create(provider):
        return RainDisplay(provider['display'], provider['config']['rain']['url'])
    
    def entity_updated(self, entity_id, entity):
        pass  # No longer using Home Assistant entities
    
    async def start(self):
        while True:
            await self.fetch_weather_data()
            self.update()
            await asyncio.sleep(300)
        
    def should_activate(self):
        if not self.weather_data:
            return False
        
        # Check if all rain chances are 5% or below
        return not all(hour_data['r'] <= 5 for hour_data in self.weather_data)

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
            
            raw_data = ujson.loads(content.decode('utf-8'))

            
            # Convert flat array to structured data
            # Format: [rain_prob, rate_mmh, rain_prob, rate_mmh, ...]
            self.weather_data = []
            current_hour = utime.localtime()[3]  # Get current hour
            for i in range(0, len(raw_data), 2):
                if i + 1 < len(raw_data):
                    rain_prob = raw_data[i]
                    rate_mmh = raw_data[i + 1]
                    hour_offset = i // 2
                    actual_hour = (current_hour + hour_offset) % 24
                    self.weather_data.append({
                        'hour': actual_hour,  # Actual hour
                        'r': rain_prob,  # Rain probability
                        'rate': rate_mmh  # Rate mm/h
                    })
            
            print(f"Weather data fetched: {len(self.weather_data)} hours")
            for hour_data in self.weather_data:
                print(f"  Hour {hour_data['hour']:02d}: Rain {hour_data['r']}%, Rate {hour_data['rate']} mm/h")
                
        except Exception as e:
            print(f"Error fetching weather data: {e}")
       
        
    def update(self):
        if self.is_active == False:
            return
        
        start_update_ms = utime.ticks_ms()
        self.__update()
        update_time_ms = utime.ticks_diff(utime.ticks_ms(), start_update_ms)
        print(f"RainDisplay: {update_time_ms}ms")
    
    def __update(self):
        if len(self.weather_data) == 0:
            return
        
        y_start = 70
               
        self.display.set_pen(self.display.create_pen(0, 0, 0))
        self.display.rectangle(0, y_start, self.display_width, self.display_height - y_start)

        self.display.set_pen(self.display.create_pen(64, 64, 64))
        self.display.rectangle(0, y_start + 20, self.display_width, 2)
        
        column_width = self.display_width / (len(self.weather_data) - 1)
        for i, hour_data in enumerate(self.weather_data):
            if i == len(self.weather_data) - 1:
                continue

            hour_number = 12 if hour_data['hour'] == 0 else hour_data['hour']
            rain_chance = hour_data['r']
            rate_mmh = hour_data['rate']
            
            sx = int(i * column_width)
            sy = y_start
            
            if i > 0:
                self.display.set_pen(self.display.create_pen(64, 64, 64))
                self.display.rectangle(sx, sy, 2, self.display_height - y_start)
            
            self.display.set_pen(self.display.create_pen(255, 255, 255))
            height = 2 * 8
            textbox.draw_textbox(self.display, f'{hour_number}', sx, sy, int(column_width), height, font='bitmap8', scale=2)
            
            sy += 35
            
            max_column_height = 70
            
            rain_color = colors.get_color_for_rain_percentage(rain_chance)
            self.display.set_pen(self.display.create_pen(rain_color[0], rain_color[1], rain_color[2]))
            height = 2 * 8
            textbox.draw_textbox(self.display, f'{rain_chance}%', sx, sy + max_column_height + 15, int(column_width), height, font='bitmap8', scale=2)
            
            self.display.set_pen(self.display.create_pen(117, 150, 148))
            
            sy += max_column_height + 40
            
            if rate_mmh > 0:
                precip_color = colors.get_color_for_precip_rate(rate_mmh)
                self.display.set_pen(self.display.create_pen(precip_color[0], precip_color[1], precip_color[2]))
                rate_label = f"{rate_mmh:.0f}"
                height = 2 * 8
                textbox.draw_textbox(self.display, rate_label, sx, sy, int(column_width), height, font='bitmap8', scale=2)

        chart_y = y_start + 24
        chart_height = 90

        self.display.set_pen(self.display.create_pen(64, 64, 64))
        self.display.rectangle(0, chart_y + chart_height, self.display_width, 2)

        normalized_data = [hour['r'] / 100 for hour in self.weather_data]

        def rain_color_fn(idx, value):
            return colors.get_color_for_rain_percentage(int(value))

        chart.draw_segmented_area(self.display, 0, chart_y, self.display_width, chart_height,
                                   [h['r'] for h in self.weather_data], normalized_data, rain_color_fn)

        chart.draw_colored_points(self.display, 0, chart_y, self.display_width, chart_height,
                                   [h['r'] for h in self.weather_data], normalized_data, rain_color_fn, radius=2)

        self.display.update()
