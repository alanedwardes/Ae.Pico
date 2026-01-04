import asyncio
import utime
import gc
import chart
import colors
import re
import textbox
import random
from httpstream import HttpRequest
from flatjson import parse_flat_json_array

def rain_color_fn(idx, value):
    # color mapping for rain percentage (expects raw 0-100)
    return colors.get_color_for_rain_percentage(int(value))

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
    def __init__(self, display, url, refresh_period_seconds):
        self.display = display
        self.url = url
        self.weather_data = []
        self.is_active = True
        self.refresh_period_seconds = refresh_period_seconds

        self.display_width, self.display_height = self.display.get_bounds()
        # Cached, precomputed arrays to reduce per-frame allocations
        self._r_values = []
        self._normalized_r = []
        self._beaufort_values = []
        self._rate_ints = []

        # Pre-allocate HTTP request helper
        self._http_request = HttpRequest(url)
    
    CREATION_PRIORITY = 1
    def create(provider):
        refresh_period = provider['config']['rain'].get('refresh_period_seconds', 300)
        return RainDisplay(provider['display'], provider['config']['rain']['url'], refresh_period)
    
    async def start(self):
        await asyncio.sleep(random.randint(5, 10))
        while True:
            await self.fetch_weather_data()
            await self.update()
            await asyncio.sleep(self.refresh_period_seconds)
        
    def should_activate(self):
        if not self.weather_data:
            return False

        # Check if any rain chances are above 5% OR any Beaufort scale is 4 or higher (moderate breeze+)
        # Data format: [hour, rain_prob, rate_mmh, wind_speed, ...]
        num_hours = len(self.weather_data) // 4
        has_rain = False
        has_high_wind = False

        for i in range(num_hours):
            idx = i * 4
            rain_prob = self.weather_data[idx + 1]
            wind_speed = self.weather_data[idx + 3]

            if rain_prob > 5:
                has_rain = True
            if wind_speed_to_beaufort(wind_speed) >= 4:
                has_high_wind = True

            if has_rain or has_high_wind:
                break

        return has_rain or has_high_wind

    async def activate(self, new_active):
        self.is_active = new_active
        if self.is_active:
            await self.update()
    
    
    async def fetch_weather_data(self):
        try:
            # Use unified HTTP request helper
            reader, writer = await self._http_request.get()

            # Stream parse JSON array without buffering entire response
            # Format: [rain_prob, rate_mmh, windSpeed10m, rain_prob, rate_mmh, windSpeed10m, ...]
            # Store as flat array: [hour, rain_prob, rate_mmh, wind_speed, hour, rain_prob, rate_mmh, wind_speed, ...]
            self.weather_data = []
            current_hour = utime.localtime()[3]  # Get current hour
            element_buffer = []
            hour_offset = 0

            async for element in parse_flat_json_array(reader):
                element_buffer.append(element)

                # Process in groups of 3 (rain_prob, rate_mmh, windSpeed10m)
                if len(element_buffer) == 3:
                    rain_prob = element_buffer[0]
                    rate_mmh = element_buffer[1]
                    wind_speed = element_buffer[2]
                    actual_hour = (current_hour + hour_offset) % 24

                    # Append as flat array: hour, rain_prob, rate_mmh, wind_speed
                    self.weather_data.append(actual_hour)
                    self.weather_data.append(rain_prob)
                    self.weather_data.append(rate_mmh)
                    self.weather_data.append(wind_speed)

                    element_buffer = []
                    hour_offset += 1

            writer.close()
            await writer.wait_closed()

            # Clean up after HTTP request
            import gc
            gc.collect()

            # Precompute and cache arrays for rendering
            # Data format: [hour, rain_prob, rate_mmh, wind_speed, ...]
            num_hours = len(self.weather_data) // 4
            if num_hours > 0:
                self._r_values = []
                self._normalized_r = []
                self._beaufort_values = []
                rate_ints = []

                for i in range(num_hours):
                    idx = i * 4
                    rain_prob = self.weather_data[idx + 1]
                    rate_mmh = self.weather_data[idx + 2]
                    wind_speed = self.weather_data[idx + 3]

                    r_int = int(rain_prob)
                    self._r_values.append(r_int)
                    self._normalized_r.append(r_int / 100)
                    self._beaufort_values.append(wind_speed_to_beaufort(wind_speed))

                    # Precompute integer mm/h to avoid float formatting during render
                    try:
                        rate_ints.append(int(rate_mmh + 0.5))
                    except TypeError:
                        rate_ints.append(int(rate_mmh))

                self._rate_ints = rate_ints
            else:
                self._r_values = []
                self._normalized_r = []
                self._beaufort_values = []
                self._rate_ints = []

            print(f"Weather data fetched: {num_hours} hours")
            for i in range(num_hours):
                idx = i * 4
                hour = self.weather_data[idx]
                rain_prob = self.weather_data[idx + 1]
                rate_mmh = self.weather_data[idx + 2]
                wind_speed = self.weather_data[idx + 3]
                beaufort_number = wind_speed_to_beaufort(wind_speed)
                print(f"  Hour {hour:02d}: Rain {rain_prob}%, Rate {rate_mmh} mm/h, Wind {wind_speed} m/s (Bft {beaufort_number})")
                
        except Exception as e:
            print(f"Error fetching weather data: {e}")
       
        
    async def update(self):
        if self.is_active == False:
            return

        start_update_ms = utime.ticks_ms()
        mem_before = gc.mem_alloc()
        await self.__update()
        update_time_ms = utime.ticks_diff(utime.ticks_ms(), start_update_ms)
        mem_after = gc.mem_alloc()
        print(f"RainDisplay: {update_time_ms}ms, mem: {mem_before} -> {mem_after} ({mem_after - mem_before:+d})")

    async def __update(self):
        if len(self.weather_data) == 0:
            return

        y_start = 70
        key_width = 30
        data_width = self.display_width - key_width
        # Use integer arithmetic for column positions to avoid float churn
        # Data format: [hour, rain_prob, rate_mmh, wind_speed, ...]
        num_points = len(self.weather_data) // 4
        denom = (num_points - 1) if num_points > 1 else 1
        column_width_int = max(1, data_width // denom)

        # Draw key column first
        self.display.rect(0, y_start, key_width, self.display_height - y_start, 0x2104, True)

        # Define row positions with proper spacing
        hour_row_y = y_start
        precip_row_y = y_start + 30
        chart_y = y_start + 60
        wind_row_y = self.display_height - 20  # Position wind speed near bottom of screen
        chart_height = wind_row_y - chart_y - 5

        # Draw key labels
        white_pen = 0xFFFF
        textbox.draw_textbox(self.display, 't', 0, hour_row_y, key_width, 16, color=white_pen, font='small')
        textbox.draw_textbox(self.display, 'mm', 0, precip_row_y, key_width, 16, color=white_pen, font='small')
        textbox.draw_textbox(self.display, '%', 0, chart_y, key_width, chart_height, color=white_pen, font='small')
        textbox.draw_textbox(self.display, 'Bft', 0, wind_row_y, key_width, 16, color=white_pen, font='small')

        # Draw separator lines
        self.display.rect(key_width, precip_row_y - 10, data_width, 2, 0x4208, True)
        self.display.rect(key_width, chart_y - 10, data_width, 2, 0x4208, True)

        # Draw data for each hour
        # Data format: [hour, rain_prob, rate_mmh, wind_speed, ...]
        for i in range(num_points):
            if i == num_points - 1:
                continue

            idx = i * 4
            hour = self.weather_data[idx]
            hour_number = 12 if hour == 0 else hour
            rate_int = self._rate_ints[i] if i < len(self._rate_ints) else int(self.weather_data[idx + 2])

            sx = key_width + (i * data_width) // denom
            next_sx = key_width + ((i + 1) * data_width) // denom if i < num_points - 1 else self.display_width
            column_width = next_sx - sx

            # Clear this column
            self.display.rect(sx, y_start, column_width, self.display_height - y_start, 0x0000, True)

            # Draw vertical separator
            if i > 0:
                self.display.rect(sx, y_start, 2, self.display_height - y_start, 0x4208, True)

            # Redraw horizontal separator lines for this column
            self.display.rect(sx, precip_row_y - 10, column_width, 2, 0x4208, True)
            self.display.rect(sx, chart_y - 10, column_width, 2, 0x4208, True)

            # Hour numbers
            textbox.draw_textbox(self.display, f'{hour_number}', sx, hour_row_y, column_width_int, 16, color=white_pen, font='small')

            # Precipitation amount
            if rate_int > 0:
                precip_color = colors.get_color_for_precip_rate(rate_int)
            else:
                precip_color = 0x632C
            textbox.draw_textbox(self.display, str(rate_int), sx, precip_row_y, column_width_int, 16, color=precip_color, font='small')

            # Beaufort scale
            beaufort_number = self._beaufort_values[i] if i < len(self._beaufort_values) else wind_speed_to_beaufort(self.weather_data[idx + 3])
            beaufort_color = colors.get_color_for_beaufort_scale(beaufort_number)
            textbox.draw_textbox(self.display, f"{beaufort_number}", sx, wind_row_y, column_width_int, 16, color=beaufort_color, font='small')
            
            await asyncio.sleep(0)

        # Draw chart segment for this column
        # We need to draw the chart segments that fall within this column
        chart.draw_segmented_area(self.display, key_width, chart_y, self.display_width - key_width, chart_height,
                                    self._r_values, self._normalized_r, rain_color_fn)
        await asyncio.sleep(0)

        chart.draw_colored_points(self.display, key_width, chart_y, self.display_width - key_width, chart_height,
                                    self._r_values, self._normalized_r, rain_color_fn, radius=2)
        await asyncio.sleep(0)

        self.display.update((0, y_start, self.display_width, self.display_height - y_start))