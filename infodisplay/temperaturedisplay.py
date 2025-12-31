import gauge
import textbox
import math
import utime
import asyncio
import gc

from httpstream import HttpRequest
from flatjson import parse_flat_json_array

class TemperatureDisplay:
    def __init__(self, display, url, refresh_period_seconds):
        self.display = display
        self.url = url
        self.temperature_data = [0, 0, 0]  # [current, min, max]
        self.refresh_period_seconds = refresh_period_seconds

        self.display_width, self.display_height = self.display.get_bounds()

        # Pre-allocate HTTP request helper
        self._http_request = HttpRequest(url)
    
    CREATION_PRIORITY = 1
    def create(provider):
        refresh_period = provider['config']['temperature'].get('refresh_period_seconds', 300)
        return TemperatureDisplay(provider['display'], provider['config']['temperature']['url'], refresh_period)
    
    async def fetch_temperature_data(self):
        try:
            # Use unified HTTP request helper
            reader, writer = await self._http_request.get()

            # Stream parse JSON array without buffering entire response
            # Format: [current, min, max]
            self.temperature_data = []
            async for element in parse_flat_json_array(reader):
                self.temperature_data.append(element)

            writer.close()
            await writer.wait_closed()

            # Clean up after HTTP request
            import gc
            gc.collect()

            print(f"Temperature data fetched: current={self.temperature_data[0]}°C, min={self.temperature_data[1]}°C, max={self.temperature_data[2]}°C")

        except Exception as e:
            print(f"Error fetching temperature data: {e}")

    async def start(self):
        while True:
            await self.fetch_temperature_data()
            self.update()
            await asyncio.sleep(self.refresh_period_seconds)
        
    def update(self):
        start_update_ms = utime.ticks_ms()
        mem_before = gc.mem_alloc()
        self.__update()
        update_time_ms = utime.ticks_diff(utime.ticks_ms(), start_update_ms)
        mem_after = gc.mem_alloc()
        print(f"TemperatureDisplay: {update_time_ms}ms, mem: {mem_before} -> {mem_after} ({mem_after - mem_before:+d})")

    def __update(self):
        if len(self.temperature_data) < 3:
            return

        current_temperature = round(float(self.temperature_data[0]))
        minimum_temperature = round(float(self.temperature_data[1]))
        maximum_temperature = round(float(self.temperature_data[2]))
        
        self.display.rect(self.display_width - 64, 0, 64, 70, 0x0000, True)
        
        position = (self.display_width - 64, 0)
        size = (64, 64)
        gauge.draw_gauge(self.display, position, size, minimum_temperature, maximum_temperature, current_temperature)
        
        # Draw current temperature in the gauge
        white_pen = 0xFFFF
        primary_scale = size[1] * 0.06
        primary_height = size[1]
        current_temp_str = f"{abs(current_temperature) if current_temperature == 0 else current_temperature:.0f}°"
        textbox.draw_textbox(self.display, current_temp_str, position[0], position[1], size[0], primary_height, color=white_pen, font='regular')
        
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
        textbox.draw_textbox(self.display, min_temp_str, extent_left, text_y, text_size_x, text_size_y, color=white_pen, font='small')
        textbox.draw_textbox(self.display, max_temp_str, centre_x, text_y, text_size_x, text_size_y, color=white_pen, font='small')

        # Render only the temperature region
        self.display.update((self.display_width - 64, 0, 64, 70))
