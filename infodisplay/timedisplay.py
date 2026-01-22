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
        
        # Cache last-rendered strings to avoid unnecessary redraws
        self._last_time_text = None   # HH:MM
        self._last_day_text = None    # Day-of-week
        self._last_sec_text = None    # SS
        self._last_ms_text = None     # M (tenths)
    
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
            self.__update()
            # Update frequently for milliseconds (approx 20fps)
            await asyncio.sleep(0.05)

    def __update(self):
        # Layout constants
        height = 70
        section_height = height // 2
        time_width = 200
        date_seconds_width = self.display_width - time_width - 64  # the temp display is 64px

        now = self.rtc.datetime()

        # Compute current texts
        time_text = '%02i:%02i' % (now[4], now[5])
        day_text = f'{self.DAYS[now[3]-1]}'
        sec_text = '%02i' % now[6]
        ms_text = '%i' % (now[7] // 100) # Tenths

        # Redraw HH:MM only when it changes
        if time_text != self._last_time_text:
            # Clear time area then draw
            self.display.rect(0, 0, time_width, height, 0x0000, True)
            textbox.draw_textbox(self.display, time_text, 0, 0, time_width, height, color=0xFFFF, font='headline', scale=1)
            self._last_time_text = time_text

        # Redraw day-of-week only when it changes
        if day_text != self._last_day_text:
            self.display.rect(time_width, 0, date_seconds_width, section_height, 0x0000, True)
            textbox.draw_textbox(self.display, day_text, time_width, 0, date_seconds_width, section_height, color=0xFFFF, font='regular', scale=1)
            self._last_day_text = day_text

        # Helper vars for layout
        sec_width = 36
        sec_height = section_height
        sec_x = time_width + (date_seconds_width - sec_width) // 2 - 6 # Shift left slightly
        
        ms_width = 15
        ms_height = section_height
        ms_x = sec_x + sec_width

        # Redraw seconds only when they change
        if sec_text != self._last_sec_text:
            self.display.rect(sec_x, section_height, sec_width, sec_height, 0x0000, True)
            textbox.draw_textbox(self.display, sec_text, sec_x, section_height, sec_width, sec_height, color=0xFFFF, font='regular', scale=1)
            self._last_sec_text = sec_text

        # Redraw MS only when they change
        if ms_text != self._last_ms_text:
            self.display.rect(ms_x, section_height, ms_width, ms_height, 0x0000, True)
            textbox.draw_textbox(self.display, ms_text, ms_x, section_height, ms_width, ms_height, color=0xFFFF, font='small', scale=1, align='left')
            self._last_ms_text = ms_text
