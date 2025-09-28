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

def wind_speed_to_beaufort(wind_speed_ms):
    """
    Convert wind speed in m/s to Beaufort scale number.
    Uses the empirical relationship: v = 0.836 * B^(3/2) m/s
    Solving for B: B = (v / 0.836)^(2/3)
    """
    if wind_speed_ms is None or wind_speed_ms < 0:
        return 0
    
    # Calculate Beaufort number using the inverse formula
    beaufort = (wind_speed_ms / 0.836) ** (2/3)
    
    # Round to nearest integer and clamp to valid range
    beaufort_rounded = round(beaufort)
    
    # Clamp to valid Beaufort scale range (0-12, with 12+ for hurricane force)
    if beaufort_rounded < 0:
        return 0
    elif beaufort_rounded > 12:
        return 12
    else:
        return beaufort_rounded

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
        
        # Check if any rain chances are above 5% OR any Beaufort scale is 4 or higher (moderate breeze+)
        has_rain = not all(hour_data['r'] <= 5 for hour_data in self.weather_data)
        has_high_wind = any(wind_speed_to_beaufort(hour_data['wind']) >= 4 for hour_data in self.weather_data)
        
        return has_rain or has_high_wind

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
            # Format: [rain_prob, rate_mmh, windSpeed10m, rain_prob, rate_mmh, windSpeed10m, ...]
            self.weather_data = []
            current_hour = utime.localtime()[3]  # Get current hour
            for i in range(0, len(raw_data), 3):
                if i + 2 < len(raw_data):
                    rain_prob = raw_data[i]
                    rate_mmh = raw_data[i + 1]
                    wind_speed = raw_data[i + 2]
                    hour_offset = i // 3
                    actual_hour = (current_hour + hour_offset) % 24
                    self.weather_data.append({
                        'hour': actual_hour,  # Actual hour
                        'r': rain_prob,  # Rain probability
                        'rate': rate_mmh,  # Rate mm/h
                        'wind': wind_speed  # Wind speed 10m
                    })
            
            print(f"Weather data fetched: {len(self.weather_data)} hours")
            for hour_data in self.weather_data:
                beaufort_number = wind_speed_to_beaufort(hour_data['wind'])
                print(f"  Hour {hour_data['hour']:02d}: Rain {hour_data['r']}%, Rate {hour_data['rate']} mm/h, Wind {hour_data['wind']} m/s (Bft {beaufort_number})")
                
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
        
        # Clear the display area
        y_start = 70
        key_width = 30
        data_width = self.display_width - key_width
        column_width = data_width / (len(self.weather_data) - 1)
        
        self.display.set_pen(self.display.create_pen(0, 0, 0))
        self.display.rectangle(0, y_start, self.display_width, self.display_height - y_start)
        
        # Draw key column
        self.display.set_pen(self.display.create_pen(32, 32, 32))
        self.display.rectangle(0, y_start, key_width, self.display_height - y_start)
        
        # Define row positions with proper spacing
        hour_row_y = y_start
        precip_row_y = y_start + 30
        chart_y = y_start + 60
        wind_row_y = self.display_height - 20  # Position wind speed near bottom of screen
        chart_height = wind_row_y - chart_y - 5
        
        # Draw key labels
        self.display.set_pen(self.display.create_pen(255, 255, 255))
        textbox.draw_textbox(self.display, 't', 0, hour_row_y, key_width, 16, font='bitmap8', scale=2)
        textbox.draw_textbox(self.display, 'mm', 0, precip_row_y, key_width, 16, font='bitmap8', scale=2)
        textbox.draw_textbox(self.display, '%', 0, chart_y, key_width, chart_height, font='bitmap8', scale=2)
        textbox.draw_textbox(self.display, 'Bft', 0, wind_row_y, key_width, 16, font='bitmap8', scale=2)
        
        # Draw separator lines
        self.display.set_pen(self.display.create_pen(64, 64, 64))
        self.display.rectangle(key_width, precip_row_y - 10, data_width, 2)
        self.display.rectangle(key_width, chart_y - 10, data_width, 2)
        
        # Draw data for each hour
        for i, hour_data in enumerate(self.weather_data):
            if i == len(self.weather_data) - 1:
                continue

            hour_number = 12 if hour_data['hour'] == 0 else hour_data['hour']
            rate_mmh = hour_data['rate']
            wind_speed = hour_data['wind']
            
            sx = int(key_width + i * column_width)
            
            # Draw vertical separator
            if i > 0:
                self.display.set_pen(self.display.create_pen(64, 64, 64))
                self.display.rectangle(sx, y_start, 2, self.display_height - y_start)
            
            # Hour numbers
            self.display.set_pen(self.display.create_pen(255, 255, 255))
            textbox.draw_textbox(self.display, f'{hour_number}', sx, hour_row_y, int(column_width), 16, font='bitmap8', scale=2)
            
            # Precipitation amount
            if rate_mmh > 0:
                precip_color = colors.get_color_for_precip_rate(rate_mmh)
            else:
                precip_color = (100, 100, 100)
            self.display.set_pen(self.display.create_pen(precip_color[0], precip_color[1], precip_color[2]))
            textbox.draw_textbox(self.display, f"{rate_mmh:.0f}", sx, precip_row_y, int(column_width), 16, font='bitmap8', scale=2)
            
            # Beaufort scale
            beaufort_number = wind_speed_to_beaufort(wind_speed)
            beaufort_color = colors.get_color_for_beaufort_scale(beaufort_number)
            self.display.set_pen(self.display.create_pen(beaufort_color[0], beaufort_color[1], beaufort_color[2]))
            textbox.draw_textbox(self.display, f"{beaufort_number}", sx, wind_row_y, int(column_width), 16, font='bitmap8', scale=2)

        # Draw chart
        normalized_data = [hour['r'] / 100 for hour in self.weather_data]
        def rain_color_fn(idx, value):
            return colors.get_color_for_rain_percentage(int(value))

        chart.draw_segmented_area(self.display, key_width, chart_y, data_width, chart_height,
                                   [h['r'] for h in self.weather_data], normalized_data, rain_color_fn)
        chart.draw_colored_points(self.display, key_width, chart_y, data_width, chart_height,
                                   [h['r'] for h in self.weather_data], normalized_data, rain_color_fn, radius=2)

        self.display.update()
