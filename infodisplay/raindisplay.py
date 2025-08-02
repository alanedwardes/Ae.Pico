try:
    import ujson
except ModuleNotFoundError:
    import json as ujson

import asyncio
import utime
import chart
import colors
import re

URL_RE = re.compile(r'(http|https)://([A-Za-z0-9-\.]+)(?:\:([0-9]+))?(.+)?')

class RainDisplay:
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
        return RainDisplay(provider['display'], provider['config']['rain']['url'], rtc)
    
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
            
            raw_data = ujson.loads(content.decode('utf-8'))
            
            # Convert flat array to structured data
            # Format: [rain_prob, temp, rain_prob, temp, ...]
            self.weather_data = []
            for i in range(0, len(raw_data), 2):
                if i + 1 < len(raw_data):
                    rain_prob = raw_data[i]
                    temp = raw_data[i + 1]
                    self.weather_data.append({
                        'h': i // 2,  # Hour
                        'r': rain_prob,  # Rain probability
                        't': temp  # Temperature
                    })
            
            print(f"Weather data fetched: {len(self.weather_data)} hours")
            for hour_data in self.weather_data:
                print(f"  Hour {hour_data['h']:02d}: Rain {hour_data['r']}%, Temp {hour_data['t']}°C")
                
        except Exception as e:
            print(f"Error fetching weather data: {e}")
       
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
        if len(self.weather_data) == 0:
            return
        
        y_start = 70
               
        self.display.set_pen(self.display.create_pen(0, 0, 0))
        self.display.rectangle(0, y_start, self.display_width, self.display_height - y_start)

        self.display.set_pen(self.display.create_pen(64, 64, 64))
        self.display.rectangle(0, y_start + 35, self.display_width, 2)
        
        self.display.set_font('bitmap8')

        column_width = self.display_width // (len(self.weather_data) - 1)
        for i, hour_data in enumerate(self.weather_data):
            if i == len(self.weather_data) - 1:
                continue

            hour_number = 12 if hour_data['h'] == 0 else hour_data['h']
            rain_chance = hour_data['r']
            temperature = hour_data['t']
            
            sx = i * column_width
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

        for px, py in chart.draw_chart(0, chart_y, self.display_width, chart_height, [hour['r'] / 100 for hour in self.weather_data], 32):
            polygon.append((int(px), int(py)))

        polygon.append((self.display_width, chart_y + chart_height))

        self.display.set_pen(self.display.create_pen(117, 150, 148))
        self.display.polygon(polygon)

        self.display.set_pen(self.display.create_pen(174, 220, 216))
        for px, py in chart.draw_chart(0, chart_y, self.display_width, chart_height, [hour['r'] / 100 for hour in self.weather_data]):
            self.display.circle(int(px), int(py), 2)

        self.display.update()
