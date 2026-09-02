import asyncio
import gc
import colors
import struct
import textbox
import table
import random
import array
from bitblt import blit_region

from httpstream import HttpRequest
from flatjson import load_array

_DAY_NAMES = ('MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT', 'SUN')
_WEEKEND_WEEKDAYS = (5, 6)

def _format_temperature(value):
    rounded = round(value)
    return f"{abs(rounded) if rounded == 0 else rounded:.0f}°"

async def _draw_text_cell(display, x, y, w, h, text, color, font_name):
    textbox.draw_textbox(display, text, x, y, w, h, color=color, background=0x000000, font=font_name)

async def _draw_today_cell(display, x, y, w, h):
    display.rect(int(x), int(y), int(w), int(h), 0x000000, True)

    tri_w = w // 3
    tri_h = h // 3
    cx = x + w // 2
    cy = y + h // 2
    pts = array.array('h', [
        -tri_w // 2, -tri_h // 2,   # Top-left
        tri_w // 2, -tri_h // 2,    # Top-right
        0, tri_h // 2               # Bottom-center
    ])
    display.poly(cx, cy, pts, 0xFFFF00, True)

async def _draw_icon_cell(display, x, y, w, h, weather_display, icon_name):
    display.rect(int(x), int(y), int(w), int(h), 0x000000, True)
    weather_display.draw_icon(icon_name, display, x, y, w, h)

class WeatherDisplay:
    def __init__(self, display, url, refresh_period_seconds, start_y, time):
        self.display = display
        self.url = url
        self.weather_data = []
        self.refresh_period_seconds = refresh_period_seconds
        self.start_y = start_y
        self.time = time

        self.display_width, self.display_height = self.display.get_bounds()
        
        # Get bytes_per_pixel dynamically
        self.bytes_per_pixel = self.display.bytes_per_pixel
        
        # Pre-allocate line buffer for blitting using a max size if needed (e.g. max icon width is 100)
        self._line_buffer = bytearray(100 * 2)

        # Pre-allocate HTTP request helper to reduce memory allocations
        self._http_request = HttpRequest(url)

        self.tsf = asyncio.ThreadSafeFlag()
    
    CREATION_PRIORITY = 2
    def create(provider):
        config = provider['config']['weather']
        refresh_period = config.get('refresh_period_seconds', 300)
        y_separator = provider['config']['display'].get('y_separator', 70)
        return WeatherDisplay(provider['display'], config['url'], refresh_period, y_separator, provider['time'])
    
    async def start(self):
        await asyncio.sleep(random.randint(5, 10))
        while True:
            await self.fetch_weather_data()
            await asyncio.sleep(self.refresh_period_seconds)
        
    def should_activate(self):
        if len(self.weather_data) == 0:
            return False
        return True

    async def activate(self):
        while True:
            await self.update()
            await self.tsf.wait()

    async def fetch_weather_data(self):
        try:
            # Use unified HTTP request helper
            async with self._http_request.get_scoped() as (reader, writer):
                # Stream parse JSON array without buffering entire response
                # Format: [code, max_temp, min_temp, rain, code, max_temp, min_temp, rain, ...]
                self.weather_data = []
                async for element in load_array(reader):
                    self.weather_data.append(element)

            # Clean up after HTTP request
            import gc
            gc.collect()

            self.tsf.set()

        except Exception as e:
            print(f"Error fetching weather data: {e}")
    
    def draw_icon(self, icon_name, framebuffer, x, y, box_width, box_height):
        try:
            with open(f'icons/weather_{icon_name}.bin', 'rb') as icon_file:
                icon_width, icon_height = struct.unpack('<HH', icon_file.read(4))
                # Center the icon in the given box
                icon_x = x + (box_width - icon_width) // 2
                icon_y = y + (box_height - icon_height) // 2

                # Calculate file size to determine bpp
                icon_file.seek(0, 2) # seek to end
                file_size = icon_file.tell()
                icon_file.seek(4) # seek back exactly following the 4-byte header

                icon_bpp = (file_size - 4) // (icon_width * icon_height)
                if icon_bpp <= 0: icon_bpp = 1
                
                icon_row_bytes = icon_width * icon_bpp
                
                # Make sure the line buffer is large enough
                if len(self._line_buffer) < icon_width * icon_bpp:
                     self._line_buffer = bytearray(icon_width * icon_bpp)

                blit_region(framebuffer, self.display_width, self.display_height, icon_bpp,
                            icon_file, 4, icon_row_bytes,
                            0, 0, icon_width, icon_height,
                            icon_x, icon_y, buffer=self._line_buffer)
        except OSError as e:
            print(f"Warning: Could not load icon '{icon_name}': {e}")
            return
            
    async def update(self):
        if len(self.weather_data) == 0:
            return

        y_start = self.start_y
        font_name = 'regular' if self.display_width > 320 else 'small'

        # Calculate number of days from data (each day has 4 values: code, max_temp, min_temp, rain)
        num_days = len(self.weather_data) // 4
        if num_days == 0:
            return

        usable_height = self.display_height - y_start
        grid = table.grid_rects(0, y_start, self.display_width, usable_height, 5, num_days)

        today_weekday = self.time.local_time()[6]
        cells = []
        for i in range(num_days):
            data_index = i * 4
            if data_index + 3 >= len(self.weather_data):
                break

            weather_code = self.weather_data[data_index]
            max_temperature = self.weather_data[data_index + 1]
            min_temperature = self.weather_data[data_index + 2]
            rain = self.weather_data[data_index + 3]

            day_x, day_y, day_w, day_h = grid[0 * num_days + i]
            icon_x, icon_y, icon_w, icon_h = grid[1 * num_days + i]
            max_x, max_y, max_w, max_h = grid[2 * num_days + i]
            min_x, min_y, min_w, min_h = grid[3 * num_days + i]
            rain_x, rain_y, rain_w, rain_h = grid[4 * num_days + i]

            if i == 0:
                cells.append((day_x, day_y, day_w, day_h, _draw_today_cell, ()))
            else:
                day_of_week = (today_weekday + i) % 7
                day_pen = 0xC8CED4 if day_of_week in _WEEKEND_WEEKDAYS else 0xFFFFFF
                cells.append((day_x, day_y, day_w, day_h, _draw_text_cell, (_DAY_NAMES[day_of_week], day_pen, font_name)))

            cells.append((icon_x, icon_y, icon_w, icon_h, _draw_icon_cell, (self, weather_code)))

            max_temp_str = _format_temperature(max_temperature)
            min_temp_str = _format_temperature(min_temperature)

            cells.append((max_x, max_y, max_w, max_h, _draw_text_cell, (max_temp_str, colors.get_color_for_temperature(max_temperature), font_name)))
            cells.append((min_x, min_y, min_w, min_h, _draw_text_cell, (min_temp_str, colors.get_color_for_temperature(min_temperature), font_name)))

            rain_color = colors.get_color_for_rain_percentage(rain)
            cells.append((rain_x, rain_y, rain_w, rain_h, _draw_text_cell, (f"{rain}%", rain_color, font_name)))

        await table.draw_cells(self.display, cells, shuffle=True)