import math
import utime
import asyncio
import gc
import textbox

class TimeDisplay:
    MONTHS = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC']
    DAYS = ['MO', 'TU', 'WE', 'TH', 'FR', 'SA', 'SU']
    
    def __init__(self, display, time_source, height):
        self.display = display
        self.time_source = time_source
        self.height = height
        
        self.display_width, self.display_height = self.display.get_bounds()
        self.display_half_width = self.display_width * 0.5
        
        # Pre-allocate strings to prevent ALL allocations during the update loop
        self._padded_numbers = ['%02i' % i for i in range(60)] # "00".."59"
        self._tenth_numbers = ['%i' % i for i in range(10)]    # "0".."9"
        
        # Cache last-rendered values
        self._last_minute = -1
        self._last_day_idx = -1
        self._last_second = -1
        self._last_tenth = -1
    
    CREATION_PRIORITY = 1
    def create(provider):
        remote_time = provider.get('remotetime.RemoteTime')
        if remote_time:
            time_source = remote_time.local_time
        else:
            print('Falling back to machine.RTC as remotetime.RemoteTime unavailable')
            import machine
            rtc = machine.RTC()
            # Adapt machine.RTC().datetime() to local_time() tuple format:
            # RTC: (year, month, day, weekday, hour, minute, second, subseconds)
            # local_time: (year, month, mday, hour, minute, second, weekday, yearday, milliseconds)
            def time_source():
                t = rtc.datetime()
                return (t[0], t[1], t[2], t[4], t[5], t[6], t[3] - 1, 0, t[7])
        y_separator = provider['config']['display'].get('y_separator', 70)
        return TimeDisplay(provider['display'], time_source, y_separator)
    
    async def start(self):
        while True:
            await self.__update()
            # Update frequently for milliseconds (approx 20fps)
            await asyncio.sleep(0.05)

    async def __update(self):
        # Layout constants
        height = self.height
        section_height = height // 2
        
        # Calculate proportional widths
        # Original: 200px time, 64px temp (fixed), rest date
        # Target: Similar proportions but flexible
        
        TEMP_WIDTH = self.height # Temp display is square, so width equals height
        available_width = self.display_width - TEMP_WIDTH
        
        # Give time display ~80% of the remaining width
        time_width = int(available_width * 0.8)
        date_seconds_width = available_width - time_width
        
        # Font scale proportional to height
        font_scale = self.height / 70.0

        now = self.time_source()
        # local_time format: (year, month, mday, hour, minute, second, weekday, yearday, milliseconds)

        # 1. HH:MM Display
        # Only re-format and re-draw if the minute has changed
        if now[4] != self._last_minute:
            self._last_minute = now[4]
            # Use pre-allocated strings
            hour_str = self._padded_numbers[now[3]]
            min_str = self._padded_numbers[now[4]]
            time_text = hour_str + ":" + min_str # String concatenation of interned strings is optimized in MicroPython
            
            # Clear time area then draw
            self.display.rect(0, 0, time_width, height, 0x000000, True)
            await textbox.draw_textbox(self.display, time_text, 0, 5, time_width, height - 5, color=0xFFFFFF, font='headline', scale=font_scale)
            
            # Render only the time region
            self.display.update((0, 0, time_width, height))

        # 2. Day Display
        # Only update if day changed
        if now[6] != self._last_day_idx:
            self._last_day_idx = now[6]
            # Use direct access
            day_text = self.DAYS[now[6]]
            
            self.display.rect(time_width, 0, date_seconds_width, section_height, 0x000000, True)
            await textbox.draw_textbox(self.display, day_text, time_width, 0, date_seconds_width, section_height, color=0xFFFFFF, font='regular', scale=font_scale, align='left')
            
            # Render only the day region
            self.display.update((time_width, 0, date_seconds_width, section_height))

        # Helper vars for layout
        sec_width = int(36 * font_scale) 
        sec_height = section_height
        sec_x = time_width
        
        ms_width = date_seconds_width - sec_width 
        ms_height = section_height
        ms_x = sec_x + sec_width

        # 3. Seconds Display
        if now[5] != self._last_second:
            self._last_second = now[5]
            # Use pre-allocated string
            if now[5] < 60:
                sec_text = self._padded_numbers[now[5]]
            else:
                sec_text = "00" # Safety fallback
            
            self.display.rect(sec_x, section_height, sec_width, sec_height, 0x000000, True)
            await textbox.draw_textbox(self.display, sec_text, sec_x, section_height, sec_width, sec_height, color=0xFFFFFF, font='regular', scale=font_scale, align='left')
            self.display.update((sec_x, section_height, sec_width, sec_height))

        # 4. Milliseconds (Tenths) Display
        tenth = (now[8] // 100) % 10 # Ensure 0-9 range
        if tenth != self._last_tenth:
            self._last_tenth = tenth
            # Use pre-allocated string
            ms_text = self._tenth_numbers[tenth]

            self.display.rect(ms_x, section_height, ms_width, ms_height, 0x000000, True)
            await textbox.draw_textbox(self.display, ms_text, ms_x, section_height, ms_width, ms_height, color=0xFFFFFF, font='small', scale=font_scale, align='left')
            self.display.update((ms_x, section_height, ms_width, ms_height))