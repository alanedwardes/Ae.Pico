import asyncio
import utime
import gc
import chart
import colors
import textbox
import random

from httpstream import HttpRequest
from flatjson import load_array

_MAX_UV = 12
_LABEL_HOURS = (0, 2, 4, 6, 8, 10, 12, 14, 16, 18, 20, 22)

def _uv_color_fn(idx, value):
    return colors.get_color_for_uv(value)

class UvDisplay:
    def __init__(self, display, url, refresh_period_seconds, start_y):
        self.display = display
        self.url = url
        self.uv_data = []
        self._normalized_data = []
        self.refresh_period_seconds = refresh_period_seconds
        self.start_y = start_y

        self.display_width, self.display_height = self.display.get_bounds()

        # Pre-allocate HTTP request helper
        self._http_request = HttpRequest(url)

        self.tsf = asyncio.ThreadSafeFlag()
    
    CREATION_PRIORITY = 1
    def create(provider):
        config = provider['config']['uv']
        refresh_period = config.get('refresh_period_seconds', 300)
        y_separator = provider['config']['display'].get('y_separator', 70)
        return UvDisplay(provider['display'], config['url'], refresh_period, y_separator)
    
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

    async def activate(self):
        while True:
            await self.update()
            await self.tsf.wait()
    
    async def fetch_uv_data(self):
        try:
            # Use unified HTTP request helper
            async with self._http_request.get_scoped() as (reader, writer):
                # Stream parse JSON array without buffering entire response
                self.uv_data = []
                async for uv_value in load_array(reader):
                    self.uv_data.append(uv_value)

            # Clean up after HTTP request
            import gc
            gc.collect()

            # Pre-compute normalized values (avoids list comprehension per update)
            self._normalized_data = [uv / _MAX_UV for uv in self.uv_data]

            self.tsf.set()
                
        except Exception as e:
            print(f"Error fetching UV data: {e}")
        
    async def update(self):
        if len(self.uv_data) == 0:
            return
        
        font_name = 'regular' if self.display_width > 320 else 'small'
        y_start = self.start_y
        
        # Calculate relative sizing
        label_height = max(16, self.display_height // 12)
        if font_name == 'regular':
            label_height = max(label_height, 22) # Ensure regular font fits
            
        num_hours = len(self.uv_data)
        # Ensure legend column and data segments are evenly distributed
        # Total units = 1 (legend) + (num_hours - 1) (chart segments) = num_hours
        unit_width = self.display_width // (num_hours if num_hours > 0 else 24)
        key_width = unit_width
        
        # data_width is the rest of the screen for the chart
        data_width = self.display_width - key_width
        denom = (num_hours - 1) if num_hours > 1 else 1
        
        # Clear the entire display area
        self.display.rect(0, y_start, self.display_width, self.display_height - y_start, 0x000000, True)


        chart_y = y_start + 5
        chart_height = self.display_height - y_start - label_height - 10
        
        # Draw colored labels column (key column) - now just color sections
        sections = [
            (0, 3, colors.get_color_for_uv(0)),
            (3, 6, colors.get_color_for_uv(3)),
            (6, 8, colors.get_color_for_uv(6)),
            (8, 11, colors.get_color_for_uv(8)),
            (11, 12, colors.get_color_for_uv(11))
        ]
        
        # Calculate vertical scale and draw sections (no text labels)
        for low_uv, high_uv, color in sections:
            y_top = chart_y + chart_height - (high_uv / _MAX_UV) * chart_height
            y_bot = chart_y + chart_height - (low_uv / _MAX_UV) * chart_height
            
            rect_h = int(y_bot - y_top)
            if rect_h > 0:
                self.display.rect(0, int(y_top), key_width, rect_h, color, True)

        # Draw horizontal grid lines across data area
        for uv_value in range(13):
            y_pos = chart_y + chart_height - (uv_value / _MAX_UV) * chart_height
            self.display.rect(key_width, int(y_pos), data_width, 1, 0x424142, True)

        # Draw hour labels at the bottom
        label_box_width = 30
        for i, hour in enumerate(_LABEL_HOURS):
            if hour < num_hours:
                sx = key_width + (hour * data_width) // denom
                
                # Draw vertical grid line
                self.display.rect(sx, chart_y, 1, chart_height, 0x424142, True)

                # Center the label on the tick mark, but clamp to screen bounds to avoid clipping
                tx = sx - (label_box_width // 2)
                if tx < 0:
                    tx = 0
                elif tx + label_box_width > self.display_width:
                    tx = self.display_width - label_box_width
                
                await textbox.draw_textbox(self.display, f'{hour:02d}', tx, self.display_height - label_height, label_box_width, label_height, color=0xFFFFFF, font=font_name, align='center')

        # Draw UV chart
        await chart.draw_segmented_area(self.display, key_width, chart_y, data_width, chart_height,
                                   self.uv_data, self._normalized_data, _uv_color_fn)

        await chart.draw_colored_points(self.display, key_width, chart_y, data_width, chart_height,
                                   self.uv_data, self._normalized_data, _uv_color_fn, radius=2)

        # Draw peak UV label on the graph (last to be on top)
        if num_hours > 0:
            max_uv = max(self.uv_data)
            if max_uv > 0:
                peak_idx = self.uv_data.index(max_uv)
                sx = key_width + (peak_idx * data_width) // denom
                normalized_uv = max_uv / _MAX_UV
                uv_y = chart_y + chart_height - (normalized_uv * chart_height)
                
                # Draw the peak UV value high above the point (dynamic offset)
                peak_offset = label_height + 5
                
                # Center-align and clamp to avoid edge clipping
                peak_box_w = 40
                tx = sx - (peak_box_w // 2)
                if tx < 0:
                    tx = 0
                elif tx + peak_box_w > self.display_width:
                    tx = self.display_width - peak_box_w
                
                ty = int(uv_y - peak_offset)
                if ty < y_start + 2:
                    ty = y_start + 2
                    
                await textbox.draw_textbox(self.display, str(max_uv), tx, ty, peak_box_w, label_height, color=0xFFFFFF, font=font_name, align='center')
        # Draw current time vertical line
        now = utime.localtime()
        current_hour = now[3]
        current_minute = now[4]
        current_time_decimal = current_hour + (current_minute / 60.0)
        
        if current_time_decimal < num_hours - 1:
            time_x = key_width + (current_time_decimal / denom) * data_width
            
            # Draw 2px light gray vertical line
            self.display.rect(int(time_x - 1), y_start, 2, self.display_height - y_start, 0x848284, True)
            
            # Find the UV value at current hour (linear interpolation for smoother movement)
            h_idx = int(current_time_decimal)
            h_frac = current_time_decimal - h_idx
            
            # Use interpolated value to match the line drawing
            current_uv = self.uv_data[h_idx] * (1 - h_frac) + self.uv_data[h_idx + 1] * h_frac
            
            # Calculate y position for the UV value
            normalized_uv = current_uv / _MAX_UV
            uv_y = chart_y + chart_height - (normalized_uv * chart_height)
            
            # Draw indicator circle
            self.display.ellipse(int(time_x), int(uv_y), 5, 5, 0x000000, True)
            self.display.ellipse(int(time_x), int(uv_y), 2, 2, 0xFFFFFF, True)

        # Draw "UV" label in top-left of the chart area
        uv_label_width = 40
        await textbox.draw_textbox(self.display, 'UV', key_width + 5, y_start + 5, uv_label_width, label_height, color=0xFFFFFF, font=font_name, align='left')

        # Render only the UV display region
        self.display.update((0, y_start, self.display_width, self.display_height - y_start))

