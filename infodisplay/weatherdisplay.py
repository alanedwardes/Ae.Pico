import asyncio
import utime
import gc
import colors
import struct
import textbox
import random
from bitblt import blit_region

from httpstream import HttpRequest
from flatjson import parse_flat_json_array

class WeatherDisplay:
    def __init__(self, display, url, refresh_period_seconds):
        self.display = display
        self.url = url
        self.weather_data = []
        self.refresh_period_seconds = refresh_period_seconds

        self.display_width, self.display_height = self.display.get_bounds()
        
        # Get bytes_per_pixel dynamically
        self.bytes_per_pixel = self.display.bytes_per_pixel
        
        # Pre-allocate line buffer for blitting using a max size if needed (e.g. max icon width is 100)
        self._line_buffer = bytearray(100 * 2)

        # Pre-allocate HTTP request helper to reduce memory allocations
        self._http_request = HttpRequest(url)

        self.tsf = asyncio.ThreadSafeFlag()
    
    CREATION_PRIORITY = 1
    def create(provider):
        refresh_period = provider['config']['weather'].get('refresh_period_seconds', 300)
        return WeatherDisplay(provider['display'], provider['config']['weather']['url'], refresh_period)
    
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
                async for element in parse_flat_json_array(reader):
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
        
        y_start = 70

        palette = []

        day_names = ['MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT', 'SUN']

        # Calculate number of days from data (each day has 4 values: code, max_temp, min_temp, rain)
        num_days = len(self.weather_data) // 4

        day_row_y = y_start
        icon_row_y = day_row_y + 15
        max_row_y = icon_row_y + 54
        min_row_y = max_row_y + 32
        rain_row_y = min_row_y + 32

        for i in range(num_days):
            data_index = i * 4
            if data_index + 3 >= len(self.weather_data):
                break

            weather_code = self.weather_data[data_index]
            max_temperature = self.weather_data[data_index + 1]
            min_temperature = self.weather_data[data_index + 2]
            rain = self.weather_data[data_index + 3]

            # Calculate column position and width to fill the screen evenly
            sx = (i * self.display_width) // num_days
            next_sx = ((i + 1) * self.display_width) // num_days
            column_width = next_sx - sx

            # Clear this column
            self.display.rect(sx, y_start, column_width, self.display_height - y_start, 0x000000, True)

            # Get current day of week (0 = Monday, 6 = Sunday)
            # Use utime to get current time and calculate day of week
            now = utime.localtime()
            # Calculate day of week (0 = Monday) and increment for each column
            day_of_week = (now[6] + i) % 7  # MicroPython already uses 0=Monday, so no conversion needed

            if day_of_week == 5 or day_of_week == 6:  # Saturday or Sunday
                day_pen = 0xC8CED4
            else:
                day_pen = 0xFFFFFF

            height = 2 * 8
            await textbox.draw_textbox(self.display, f"{day_names[day_of_week]}", sx, day_row_y, column_width, height, color=day_pen, font='small')

            icon = self.draw_icon(weather_code, self.display, sx, icon_row_y, column_width, 50)
            # icon is blitted directly; no color state

            # Format temperatures, avoiding "-0" display
            max_temp_rounded = round(max_temperature)
            min_temp_rounded = round(min_temperature)
            max_temp_str = f"{abs(max_temp_rounded) if max_temp_rounded == 0 else max_temp_rounded:.0f}°"
            min_temp_str = f"{abs(min_temp_rounded) if min_temp_rounded == 0 else min_temp_rounded:.0f}°"

            height = 2 * 8
            await textbox.draw_textbox(self.display, max_temp_str, sx, max_row_y, column_width, height, color=colors.get_color_for_temperature(max_temperature), font='small')

            height = 2 * 8
            await textbox.draw_textbox(self.display, min_temp_str, sx, min_row_y, column_width, height, color=colors.get_color_for_temperature(min_temperature), font='small')

            rain_color = colors.get_color_for_rain_percentage(rain)
            height = 2 * 8
            await textbox.draw_textbox(self.display, f"{rain}%", sx, rain_row_y, column_width, height, color=rain_color, font='small')

            # Update just this column
            self.display.update((sx, y_start, column_width, self.display_height - y_start))

            # Allow other work to continue
            await asyncio.sleep(0)