import math
import utime
import asyncio
import gc
import textbox

class TimeDisplay:
    MONTHS = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC']
    DAYS = ['MO', 'TU', 'WE', 'TH', 'FR', 'SA', 'SU']
    
    def __init__(self, display, rtc):
        self.display = display
        self.rtc = rtc
        
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
        rtc = provider.get('remotetime.RemoteTime')
        if not rtc:
            print('Falling back to machine.RTC as remotetime.Remotetime unavailable')
            import machine
            rtc = machine.RTC()
        return TimeDisplay(provider['display'], rtc)
    
    async def start(self):
        while True:
            await self.__update()
            # Update frequently for milliseconds (approx 20fps)
            await asyncio.sleep(0.05)

    async def __update(self):
        # Layout constants
        height = 70
        section_height = height // 2
        time_width = 200
        date_seconds_width = self.display_width - time_width - 64  # the temp display is 64px

        now = self.rtc.datetime()
        # datetime format: (year, month, day, weekday, hour, minute, second, subsecond)
        
        # 1. HH:MM Display
        # Only re-format and re-draw if the minute has changed
        if now[5] != self._last_minute:
            self._last_minute = now[5]
            # Use pre-allocated strings
            hour_str = self._padded_numbers[now[4]]
            min_str = self._padded_numbers[now[5]]
            time_text = hour_str + ":" + min_str # String concatenation of interned strings is optimized in MicroPython
            
            # Clear time area then draw
            self.display.rect(0, 0, time_width, height, 0x0000, True)
            await textbox.draw_textbox(self.display, time_text, 0, 10, time_width, height - 10, color=0xFFFF, font='headline', scale=1)
            
            # Render only the time region
            self.display.update((0, 0, time_width, height))

        # 2. Day Display
        # Only update if day changed
        if now[3] != self._last_day_idx:
            self._last_day_idx = now[3]
            # Use direct access
            day_text = self.DAYS[now[3]-1]
            
            self.display.rect(time_width, 0, date_seconds_width, section_height, 0x0000, True)
            await textbox.draw_textbox(self.display, day_text, time_width, 0, date_seconds_width, section_height, color=0xFFFF, font='regular', scale=1)
            
            # Render only the day region
            self.display.update((time_width, 0, date_seconds_width, section_height))

        # Helper vars for layout
        sec_width = 36
        sec_height = section_height
        sec_x = time_width + (date_seconds_width - sec_width) // 2 - 6 # Shift left slightly
        
        ms_width = 15
        ms_height = section_height
        ms_x = sec_x + sec_width

        # 3. Seconds Display
        if now[6] != self._last_second:
            self._last_second = now[6]
            # Use pre-allocated string
            if now[6] < 60:
                sec_text = self._padded_numbers[now[6]]
            else:
                sec_text = "00" # Safety fallback
            
            self.display.rect(sec_x, section_height, sec_width, sec_height, 0x0000, True)
            await textbox.draw_textbox(self.display, sec_text, sec_x, section_height, sec_width, sec_height, color=0xFFFF, font='regular', scale=1)
            self.display.update((sec_x, section_height, sec_width, sec_height))

        # 4. Milliseconds (Tenths) Display
        tenth = (now[7] // 100) % 10 # Ensure 0-9 range
        if tenth != self._last_tenth:
            self._last_tenth = tenth
            # Use pre-allocated string
            ms_text = self._tenth_numbers[tenth]

            self.display.rect(ms_x, section_height, ms_width, ms_height, 0x0000, True)
            await textbox.draw_textbox(self.display, ms_text, ms_x, section_height, ms_width, ms_height, color=0xFFFF, font='small', scale=1, align='left')
            self.display.update((ms_x, section_height, ms_width, ms_height))