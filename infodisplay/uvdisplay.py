import asyncio
import utime
import gc
import chart
import colors
import textbox
import random

from httpstream import HttpRequest
from flatjson import parse_flat_json_array

class UvDisplay:
    def __init__(self, display, url, refresh_period_seconds):
        self.display = display
        self.url = url
        self.uv_data = []
        self.is_active = True
        self.refresh_period_seconds = refresh_period_seconds

        self.display_width, self.display_height = self.display.get_bounds()

        # Pre-allocate HTTP request helper
        self._http_request = HttpRequest(url)
    
    CREATION_PRIORITY = 1
    def create(provider):
        refresh_period = provider['config']['uv'].get('refresh_period_seconds', 300)
        return UvDisplay(provider['display'], provider['config']['uv']['url'], refresh_period)
    
    async def start(self):
        await asyncio.sleep(random.randint(5, 10))
        while True:
            await self.fetch_uv_data()
            await asyncio.sleep(self.refresh_period_seconds)
        
    def should_activate(self):
        if not self.uv_data:
            return False
               
        first_idx = None
        last_idx = None
        for i, v in enumerate(self.uv_data):
            if v != 0 and first_idx is None:
                first_idx = i
            if v != 0:
                last_idx = i
        if first_idx is None or last_idx is None:
            return True
        now = utime.localtime()
        current_time = now[3] + (now[4] / 60.0)
        if current_time < (first_idx - 1.0):
            return False
        if current_time > (last_idx + 1.0):
            return False
        return True

    async def activate(self, new_active):
        self.is_active = new_active
        if self.is_active:
            self.update()
    
    async def fetch_uv_data(self):
        try:
            # Use unified HTTP request helper
            reader, writer = await self._http_request.get()

            # Stream parse JSON array without buffering entire response
            self.uv_data = []
            async for uv_value in parse_flat_json_array(reader):
                self.uv_data.append(uv_value)

            writer.close()
            await writer.wait_closed()

            # Clean up after HTTP request
            import gc
            gc.collect()
                
        except Exception as e:
            print(f"Error fetching UV data: {e}")
        
    def update(self):
        if self.is_active == False:
            return

        self.__update()
   
    def __update(self):
        if len(self.uv_data) == 0:
            return
        
        y_start = 70
               
        self.display.rect(0, y_start, self.display_width, self.display_height - y_start, 0x0000, True)

        # Display specific hours: 00, 06, 12, 18
        target_hours = [0, 6, 12, 18]
        display_hours = []
        hour_positions = []
        
        for hour in target_hours:
            if hour < len(self.uv_data):
                display_hours.append(self.uv_data[hour])
                hour_positions.append(hour)
        
        # Draw hour labels for every 2nd hour (0, 2, 4, 6, 8, 10, 12, 14, 16, 18, 20, 22)
        # Since we show every other UV value above, we need to align with those positions
        label_hours = [0, 2, 4, 6, 8, 10, 12, 14, 16, 18, 20, 22]
        label_width = self.display_width // 12  # 12 UV values shown above
        
        for i, hour in enumerate(label_hours):
            # Map hours to positions: 0->0, 2->1, 4->2, 6->3, 8->4, 10->5, 12->6, 14->7, 16->8, 18->9, 20->10, 22->11
            position = hour // 2
            sx = position * label_width
            
            textbox.draw_textbox(self.display, f'{hour:02d}', sx, self.display_height - 16, label_width, 16, color=0xFFFF, font='small')

        chart_y = y_start + 20  # Move chart up to start after UV values
        chart_height = self.display_height - y_start - 40  # Make chart fill more space
        
        # Draw vertical grid lines after chart area is defined
        for i, hour in enumerate(label_hours):
            if i > 0:  # Skip first line
                position = hour // 2
                sx = position * label_width
                # Calculate the top of the chart area (UV 12 line)
                chart_top = chart_y + chart_height - (12 / 12.0) * chart_height  # UV 12 line
                # Extend to bottom of screen
                self.display.rect(sx, int(chart_top), 1, self.display_height - int(chart_top), 0x4208, True)

        # Draw horizontal grid lines for all UV levels 0-12
        for uv_value in range(13):  # 0-12 inclusive
            # Calculate Y position (invert because 0 is at top)
            y_pos = chart_y + chart_height - (uv_value / 12.0) * chart_height
            
            # Draw horizontal grid line
            self.display.rect(0, int(y_pos), self.display_width, 1, 0x4208, True)
        
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
            y_pos = chart_y + chart_height - (uv_value / 12) * chart_height
            
            # Draw label on the left
            textbox.draw_textbox(self.display, label, 0, y_pos - 8, 48, 16, color=0xFFFF, font='small', align='left')

        # Calculate spacing for 12 values (every other data point)
        label_width = self.display_width // 12
        
        for i in range(0, len(self.uv_data), 2):  # Step by 2 to get every other value
            uv = self.uv_data[i]
            label_index = i // 2  # Index for positioning
            x_pos = label_index * label_width
            textbox.draw_textbox(self.display, str(uv), x_pos, y_start + 5, label_width, 16, color=0xFFFF, font='small')

        # Normalize UV values for chart (max UV is 12)
        max_uv_value = 12  # Fixed maximum
        normalized_data = [uv / max_uv_value for uv in self.uv_data]
        
        # Shared segmented area and colored points
        def uv_color_fn(idx, value):
            return colors.get_color_for_uv(value)

        chart.draw_segmented_area(self.display, 0, chart_y, self.display_width, chart_height,
                                   self.uv_data, normalized_data, uv_color_fn)

        chart.draw_colored_points(self.display, 0, chart_y, self.display_width, chart_height,
                                   self.uv_data, normalized_data, uv_color_fn, radius=2)

        # Draw current time vertical line
        if len(self.uv_data) > 0:
            now = utime.localtime()
            current_hour = now[3]  # Hour from time tuple
            current_minute = now[4]  # Minute from time tuple
            
            # Calculate position for current time with minute precision
            # Convert to decimal hours (e.g., 2:30 = 2.5 hours)
            current_time_decimal = current_hour + (current_minute / 60.0)
            
            # Since we show every other UV value (step=2), we need to map the time to the correct position
            if current_hour < len(self.uv_data):
                # Calculate x position based on decimal time
                time_x = (current_time_decimal / len(self.uv_data)) * self.display_width
                
                # Draw 2px light gray vertical line
                self.display.rect(int(time_x - 1), y_start, 2, self.display_height - y_start, 0x8410, True)
                
                # Find the UV value at current hour (still use hour for data lookup)
                current_uv = self.uv_data[current_hour]
                
                # Calculate y position for the UV value
                normalized_uv = current_uv / max_uv_value
                uv_y = chart_y + chart_height - (normalized_uv * chart_height)
                
                # Draw 2px black circle with 1px white circle inside
                self.display.ellipse(int(time_x), int(uv_y), 5, 5, 0x0000, True)
                self.display.ellipse(int(time_x), int(uv_y), 2, 2, 0xFFFF, True)

        # Render only the UV display region (below the time/temperature displays)
        self.display.update((0, y_start, self.display_width, self.display_height - y_start))
