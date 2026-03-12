import gauge
import textbox
import math
import utime
import asyncio
import gc
import random

from httpstream import HttpRequest
from flatjson import load_array

class TemperatureDisplay:
    def __init__(self, display, url, refresh_period_seconds, height):
        self.display = display
        self.url = url
        self.temperature_data = [0, 0, 0]  # [current, min, max]
        self.refresh_period_seconds = refresh_period_seconds
        self.height = height

        self.display_width, self.display_height = self.display.get_bounds()

        # Pre-allocate HTTP request helper
        self._http_request = HttpRequest(url)
    
    CREATION_PRIORITY = 1
    def create(provider):
        config = provider['config']['temperature']
        refresh_period = config.get('refresh_period_seconds', 300)
        y_separator = provider['config']['display'].get('y_separator', 70)
        return TemperatureDisplay(provider['display'], config['url'], refresh_period, y_separator)
    
    async def fetch_temperature_data(self):
        try:
            # Use unified HTTP request helper
            reader, writer = await self._http_request.get()

            # Stream parse JSON array into pre-allocated list
            # Format: [current, min, max]
            i = 0
            async for element in load_array(reader):
                if i < 3:
                    self.temperature_data[i] = element
                i += 1

            writer.close()
            await writer.wait_closed()

            # Clean up after HTTP request
            import gc
            gc.collect()

            print(f"Temperature data fetched: current={self.temperature_data[0]}°C, min={self.temperature_data[1]}°C, max={self.temperature_data[2]}°C")

        except Exception as e:
            print(f"Error fetching temperature data: {e}")

    async def start(self):
        await asyncio.sleep(random.randint(5, 10))
        while True:
            await self.fetch_temperature_data()
            await self.update()
            await asyncio.sleep(self.refresh_period_seconds)
        
    async def update(self):
        await self.__update()

    async def __update(self):
        if len(self.temperature_data) < 3:
            return

        current_temperature = round(float(self.temperature_data[0]))
        minimum_temperature = round(float(self.temperature_data[1]))
        maximum_temperature = round(float(self.temperature_data[2]))
        
        self.display.rect(self.display_width - 64, 0, 64, self.height, 0x000000, True)
        
        position = (self.display_width - 64, 0)
        size = (64, 64)
        gauge.draw_gauge(self.display, position, size, minimum_temperature, maximum_temperature, current_temperature)
        
        # Draw current temperature in the gauge
        white_pen = 0xFFFFFF
        primary_scale = size[1] * 0.06
        primary_height = size[1]
        current_temp_str = f"{abs(current_temperature) if current_temperature == 0 else current_temperature:.0f}°"
        await textbox.draw_textbox(self.display, current_temp_str, position[0], position[1], size[0], primary_height, color=white_pen, font='regular')
        
        # Draw min/max labels under the gauge
        centre_x = size[0] / 2 + position[0]
        centre_y = size[1] / 2 + position[1]
        extent_left = centre_x - size[1] * 0.5
        text_y = int(position[1] + size[1] * 0.75)
        text_size_x = size[1] * 0.5
        text_scale = max(1, math.ceil(size[1] * 0.02))
        text_height = 8 * text_scale
        text_size_y = text_height + 4
        min_temp_str = f"{abs(minimum_temperature) if minimum_temperature == 0 else minimum_temperature:.0f}°"
        max_temp_str = f"{abs(maximum_temperature) if maximum_temperature == 0 else maximum_temperature:.0f}°"
        await textbox.draw_textbox(self.display, min_temp_str, extent_left, text_y, text_size_x, text_size_y, color=white_pen, font='small')
        await textbox.draw_textbox(self.display, max_temp_str, centre_x, text_y, text_size_x, text_size_y, color=white_pen, font='small')

        # Render only the temperature region
        self.display.update((self.display_width - 64, 0, 64, self.height))
