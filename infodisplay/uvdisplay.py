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

class UvDisplay:
    def __init__(self, display, url, rtc=None):
        self.display = display
        self.url = url
        self.rtc = rtc
        self.uv_data = []
        self.is_active = True
        
        self.display_width, self.display_height = self.display.get_bounds()
    
    CREATION_PRIORITY = 1
    def create(provider):
        rtc = provider.get('remotetime.RemoteTime')
        if not rtc:
            print('Falling back to machine.RTC as remotetime.Remotetime unavailable')
            import machine
            rtc = machine.RTC()
        return UvDisplay(provider['display'], provider['config']['uv']['url'], rtc)
    
    def entity_updated(self, entity_id, entity):
        pass  # No longer using Home Assistant entities
    
    async def start(self):
        while True:
            await self.fetch_uv_data()
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
    
    async def fetch_uv_data(self):
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
                print(f"Failed to fetch UV data: {status_code}")
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
            
            self.uv_data = ujson.loads(content.decode('utf-8'))
            print(f"UV data fetched: {self.uv_data}")
                
        except Exception as e:
            print(f"Error fetching UV data: {e}")
       
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
        print(f"UvDisplay: {update_time_ms}ms")
   
    def __update(self):
        if len(self.uv_data) == 0:
            return
        
        y_start = 70
               
        self.display.set_pen(self.display.create_pen(0, 0, 0))
        self.display.rectangle(0, y_start, self.display_width, self.display_height - y_start)

        self.display.set_font('bitmap8')

        # Display specific hours: 00, 06, 12, 18
        target_hours = [0, 6, 12, 18]
        display_hours = []
        hour_positions = []
        
        for hour in target_hours:
            if hour < len(self.uv_data):
                display_hours.append(self.uv_data[hour])
                hour_positions.append(hour)
        
        # Draw hour labels for every 6th hour (0, 6, 12, 18)
        # Since we show every other UV value above, we need to align with those positions
        label_hours = [0, 6, 12, 18]
        label_width = self.display_width // 12  # 12 UV values shown above
        
        for i, hour in enumerate(label_hours):
            # Map hours to positions: 0->0, 6->3, 12->6, 18->9
            position = hour // 2
            sx = position * label_width
            
            self.display.set_pen(self.display.create_pen(255, 255, 255))
            self.draw_text(f"{hour:02d}", sx, self.display_height - 15, label_width, scale=1)

        chart_y = y_start + 20  # Move chart up to start after UV values
        chart_height = self.display_height - y_start - 35  # Make chart fill more space
        
        # Draw vertical grid lines after chart area is defined
        for i, hour in enumerate(label_hours):
            if i > 0:  # Skip first line
                position = hour // 2
                sx = position * label_width
                self.display.set_pen(self.display.create_pen(64, 64, 64))
                # Calculate the top of the chart area (UV 12 line)
                chart_top = chart_y + chart_height - (12 / 12.0) * chart_height  # UV 12 line
                # Extend to bottom of screen
                self.display.rectangle(sx, int(chart_top), 1, self.display_height - int(chart_top))

        # Draw horizontal grid lines for all UV levels 0-12
        for uv_value in range(13):  # 0-12 inclusive
            # Calculate Y position (invert because 0 is at top)
            y_pos = chart_y + chart_height - (uv_value / 12.0) * chart_height
            
            # Draw horizontal grid line
            self.display.set_pen(self.display.create_pen(64, 64, 64))
            self.display.rectangle(0, int(y_pos), self.display_width, 1)
        
        # Draw labels for specific UV levels
        uv_levels = [
            (0.5, "LOW"),
            (3.5, "MODERATE"), 
            (6.5, "HIGH"),
            (8.5, "VERY HIGH"),
            (11.5, "EXTREME")
        ]
        
        for uv_value, label in uv_levels:
            # Calculate Y position (invert because 0 is at top)
            y_pos = chart_y + chart_height - (uv_value / 12.0) * chart_height
            
            # Draw label on the left
            self.display.set_pen(self.display.create_pen(255, 255, 255))
            self.display.text(label, 0, int(y_pos - 3), scale=1)

        # Display UV values above the graph
        if self.uv_data:
            # Calculate spacing for 12 values (every other data point)
            label_width = self.display_width // 12
            
            for i in range(0, len(self.uv_data), 2):  # Step by 2 to get every other value
                uv = self.uv_data[i]
                label_index = i // 2  # Index for positioning
                x_pos = label_index * label_width
                self.display.set_pen(self.display.create_pen(255, 255, 255))
                self.display.text(f"{uv}", x_pos, y_start + 5, scale=1)

        # Normalize UV values for chart (max UV is 12)
        max_uv_value = 12  # Fixed maximum
        normalized_data = [uv / max_uv_value for uv in self.uv_data]
        
        # Get chart points for both polygon and circles
        chart_points = list(chart.draw_chart(0, chart_y, self.display_width, chart_height, normalized_data, step=2))
        
        if len(chart_points) > 1:
            # Create polygons for each UV color zone using the same chart points as circles
            current_polygon = []
            current_color = None
            
            # Start at the first chart point
            first_x = int(chart_points[0][0])
            current_polygon.append((first_x, chart_y + chart_height))
            
            for px, py in chart_points:
                data_index = min(len(self.uv_data) - 1, int(px / (self.display_width / len(self.uv_data))))
                uv = self.uv_data[data_index]
                uv_color = colors.get_color_for_uv(uv)
                
                # If color changes, draw current polygon and start new one
                if current_color is not None and current_color != uv_color:
                    # Complete current polygon
                    current_polygon.append((int(px), int(py)))
                    current_polygon.append((int(px), chart_y + chart_height))
                    
                    # Draw filled polygon with 50% transparency
                    transparent_color = tuple(c // 2 for c in current_color)
                    self.display.set_pen(self.display.create_pen(*transparent_color))
                    self.display.polygon(current_polygon)
                    
                    # Start new polygon
                    current_polygon = [(int(px), chart_y + chart_height), (int(px), int(py))]
                    current_color = uv_color
                else:
                    current_polygon.append((int(px), int(py)))
                    current_color = uv_color
            
            # Draw final polygon
            if current_polygon:
                last_x = int(chart_points[-1][0])
                current_polygon.append((last_x, chart_y + chart_height))
                transparent_color = tuple(c // 2 for c in current_color)
                self.display.set_pen(self.display.create_pen(*transparent_color))
                self.display.polygon(current_polygon)
        
        # Draw chart circles on top using the same points
        for px, py in chart_points:
            data_index = min(len(self.uv_data) - 1, int(px / (self.display_width / len(self.uv_data))))
            uv = self.uv_data[data_index]
            self.display.set_pen(self.display.create_pen(*colors.get_color_for_uv(uv)))
            self.display.circle(int(px), int(py), 2)

        # Draw current time vertical line
        if self.rtc and len(self.uv_data) > 0:
            now = self.rtc.datetime()
            current_hour = now[4]  # Hour from datetime tuple
            current_minute = now[5]  # Minute from datetime tuple
            
            # Calculate position for current time with minute precision
            # Convert to decimal hours (e.g., 2:30 = 2.5 hours)
            current_time_decimal = current_hour + (current_minute / 60.0)
            
            # Since we show every other UV value (step=2), we need to map the time to the correct position
            if current_hour < len(self.uv_data):
                # Calculate x position based on decimal time
                time_x = (current_time_decimal / len(self.uv_data)) * self.display_width
                
                # Draw 2px light gray vertical line
                self.display.set_pen(self.display.create_pen(128, 128, 128))
                self.display.rectangle(int(time_x - 1), y_start, 2, self.display_height - y_start)
                
                # Find the UV value at current hour (still use hour for data lookup)
                current_uv = self.uv_data[current_hour]
                
                # Calculate y position for the UV value
                normalized_uv = current_uv / max_uv_value
                uv_y = chart_y + chart_height - (normalized_uv * chart_height)
                
                # Draw 2px black circle with 1px white circle inside
                self.display.set_pen(self.display.create_pen(0, 0, 0))
                self.display.circle(int(time_x), int(uv_y), 5)
                
                self.display.set_pen(self.display.create_pen(255, 255, 255))
                self.display.circle(int(time_x), int(uv_y), 2)

        self.display.update()
