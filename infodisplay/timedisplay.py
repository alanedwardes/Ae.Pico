import math
import asyncio
import gc
import framebuf
import textbox

from bmfont import draw_text, measure_text

class _Cell:
    """Minimal offscreen render target compatible with bmfont.draw_text
    (which finds the pixel buffer via the _framebuffer attribute)."""
    def __init__(self, w, h, bytes_per_pixel, mode):
        self.bytes_per_pixel = bytes_per_pixel
        self._framebuffer = bytearray(w * h * bytes_per_pixel)
        self.fb = framebuf.FrameBuffer(self._framebuffer, w, h, mode)

class TimeDisplay:
    MONTHS = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC']
    DAYS = ['MO', 'TU', 'WE', 'TH', 'FR', 'SA', 'SU']

    def __init__(self, display, time, height, show_milliseconds):
        self.display = display
        self.time = time
        self.height = height
        self.show_milliseconds = show_milliseconds

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
        self._last_mday = -1
        self._last_month = -1

        # Layout is static -- compute it once instead of on every 50ms tick.
        # Original proportions: 200px time, 64px temp (fixed), rest date.
        self.section_height = height // 2
        temp_width = height  # Temp display is square, so width equals height
        available_width = self.display_width - temp_width
        # Give time display ~80% of the remaining width
        self.time_width = int(available_width * 0.8)
        self.date_seconds_width = available_width - self.time_width
        # Font scale proportional to height
        self.font_scale = height / 70.0
        self.sec_x = self.time_width
        if self.show_milliseconds:
            self.sec_width = int(36 * self.font_scale)
            self.ms_x = self.sec_x + self.sec_width
            self.ms_width = self.date_seconds_width - self.sec_width
        else:
            self.sec_width = self.date_seconds_width
            self.ms_x = self.sec_x + self.sec_width
            self.ms_width = 0

        # Pre-built update regions (a fresh tuple per tick is avoidable churn)
        self._time_region = (0, 0, self.time_width, height)
        self._cal_region = (self.time_width, 0, self.date_seconds_width, self.section_height)
        self._sec_region = (self.sec_x, self.section_height, self.sec_width, self.section_height)
        self._ms_region = (self.ms_x, self.section_height, self.ms_width, self.section_height)

        # Prerendered '0'-'9' cells for the tenths box, built lazily on
        # first render (fonts load from flash on first use)
        self._tenth_cells = None
        self._tenth_x = 0
        self._tenth_y = 0

    CREATION_PRIORITY = 2
    def create(provider):
        display_config = provider['config']['display']
        y_separator = display_config.get('y_separator', 70)
        show_milliseconds = display_config.get('show_milliseconds', True)
        return TimeDisplay(provider['display'], provider['time'], y_separator, show_milliseconds)

    async def start(self):
        if not self.show_milliseconds:
            while True:
                await self.update()
                await asyncio.sleep(1)
        else:
            while True:
                await self.update()
                # Update frequently for milliseconds (approx 20fps)
                await asyncio.sleep(0.05)

    def _build_tenth_cells(self):
        """Pre-render '0'-'9' for the tenths box.

        The tenths digit redraws at 10 Hz forever, and rendering it
        through textbox costs a measure, glyph reads from the font page
        and ~1.5KB of allocation per tick. A prerendered cell makes the
        tick a single allocation-free C blit. Placement math mirrors
        textbox.draw_textbox(align='left', valign='center') exactly so
        output is pixel-identical (guarded by timedisplay_check.py).
        """
        font, pages = textbox.get_font('small')
        s = max(0.000001, float(self.font_scale))
        if s < 1.0:
            up, down = 1, max(1, int(round(1.0 / s)))
        else:
            up, down = max(1, int(round(s))), 1

        box_x, box_y = self.ms_x, self.section_height
        box_w, box_h = self.ms_width, self.section_height
        line_h = (font.line_height * up) // down
        origin_y = math.floor(box_y + (box_h - line_h) * 0.5)

        # Union of the ten digits' ink boxes in screen coords: every cell
        # is this size, so blitting a new digit fully covers the old one
        top = None
        bottom = None
        right = box_x
        for d in range(10):
            w, h, mx, my = measure_text(font, self._tenth_numbers[d])
            my_s = origin_y + (my * up) // down
            if top is None or my_s < top: top = my_s
            if bottom is None or my_s + h > bottom: bottom = my_s + h
            if box_x + w > right: right = box_x + w
        if top is None:
            return None
        ux = box_x
        uy = max(top, box_y)
        cw = min(right, box_x + box_w) - ux
        ch = min(bottom, box_y + box_h) - uy
        if cw <= 0 or ch <= 0:
            return None  # box too small to prerender; keep the textbox path

        bpp = self.display.bytes_per_pixel
        mode = self.display.mode
        clip = (box_x - ux, box_y - uy, box_w, box_h)
        linebuf = self.display.get_scratch_buffer(font.scale_w)
        cells = []
        for d in range(10):
            w, h, mx, my = measure_text(font, self._tenth_numbers[d])
            cell = _Cell(cw, ch, bpp, mode)
            origin_x = math.floor(box_x - (mx * up) // down) - ux
            draw_text(cell, cw, ch, font, pages, self._tenth_numbers[d],
                      origin_x, origin_y - uy,
                      True, up, down, 0xFFFFFF, linebuf, clip)
            cells.append(cell)
        self._tenth_x = ux
        self._tenth_y = uy
        return cells

    async def update(self):
        height = self.height
        section_height = self.section_height
        time_width = self.time_width
        font_scale = self.font_scale

        now = self.time.local_time()

        # 1. HH:MM Display
        # Only re-format and re-draw if the minute has changed
        if now[4] != self._last_minute:
            self._last_minute = now[4]
            # Use pre-allocated strings
            hour_str = self._padded_numbers[now[3]]
            min_str = self._padded_numbers[now[4]]
            time_text = hour_str + ":" + min_str # String concatenation of interned strings is optimized in MicroPython

            await textbox.draw_textbox(self.display, time_text, 0, 5, time_width, height - 5, color=0xFFFFFF, font='headline', scale=font_scale, background=0x000000)

            # Render only the time region
            self.display.update(self._time_region)

        # 2. Day / Date / Month Display
        day_region_changed = (
            now[6] != self._last_day_idx
            or now[2] != self._last_mday
            or now[1] != self._last_month
        )
        if day_region_changed:
            self._last_day_idx = now[6]
            self._last_mday = now[2]
            self._last_month = now[1]

            cal_x = time_width
            cal_y = 0
            cal_w = self.date_seconds_width
            cal_h = section_height
            row_h = cal_h // 2

            day_date_text = self.DAYS[now[6]] + ' ' + str(now[2])
            month_text = self.MONTHS[now[1] - 1]

            await textbox.draw_textbox(self.display, day_date_text, cal_x, cal_y, cal_w, row_h, color=0xFFFFFF, font='small', scale=font_scale, background=0x000000)
            await textbox.draw_textbox(self.display, month_text, cal_x, cal_y + row_h, cal_w, row_h, color=0xFFFFFF, font='small', scale=font_scale, background=0x000000)

            self.display.update(self._cal_region)

        # 3. Seconds Display
        if now[5] != self._last_second:
            self._last_second = now[5]
            # Use pre-allocated string
            if now[5] < 60:
                sec_text = self._padded_numbers[now[5]]
            else:
                sec_text = "00" # Safety fallback

            sec_align = 'left' if self.show_milliseconds else 'center'
            await textbox.draw_textbox(self.display, sec_text, self.sec_x, section_height, self.sec_width, section_height, color=0xFFFFFF, font='regular', scale=font_scale, align=sec_align, background=0x000000)
            self.display.update(self._sec_region)

        # 4. Milliseconds (Tenths) Display
        if not self.show_milliseconds:
            return
        tenth = (now[8] // 100) % 10 # Ensure 0-9 range
        if tenth != self._last_tenth:
            self._last_tenth = tenth

            if self._tenth_cells is None:
                # () = build declined (box too small): don't retry per tick
                self._tenth_cells = self._build_tenth_cells() or ()

            if self._tenth_cells:
                self.display.blit(self._tenth_cells[tenth].fb, self._tenth_x, self._tenth_y)
            else:
                await textbox.draw_textbox(self.display, self._tenth_numbers[tenth], self.ms_x, section_height, self.ms_width, section_height, color=0xFFFFFF, font='small', scale=font_scale, align='left', background=0x000000)
            self.display.update(self._ms_region)
