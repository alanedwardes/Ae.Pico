import utime
import asyncio
import gc
import textbox
import table
import random
from httpstream import HttpRequest
from flatjson import load_array

def get_color_for_train_status(status, delay_minutes):
    """Get color for train status based on status string and delay minutes."""
    if status == 'cancelled':
        return 0xF80000  # Red for cancelled

    # On time (scheduled, estimated with 0 delay, or no delay info)
    if delay_minutes is None or delay_minutes == 0:
        return 0xFFFFFF  # White for on time

    # Late delays — yellow to amber only, red reserved for cancelled
    if delay_minutes <= 5:
        return 0xFED800  # Yellow for minor delay (1-5 min)
    elif delay_minutes <= 15:
        return 0xFFBF00  # Gold for moderate delay (6-15 min)
    elif delay_minutes <= 30:
        return 0xFF9900  # Amber for significant delay (16-30 min)
    else:
        return 0xFF8800  # Dark amber for major delay (>30 min)

# API format: flat array, 8 fields per departure
# [scheduled_time, destination, platform, status, delay_minutes, train_class, expected_time, toc_code]
#   scheduled_time:  HH:mm UK local string
#   destination:     display name string
#   platform:        platform string, 'TBC' if suppressed, '-' if unallocated
#   status:          'scheduled' | 'late' | 'early' | 'cancelled'
#   delay_minutes:   null when on-time/cancelled; positive=int late, negative=int early
#   train_class:     class string, '-' if unknown
#   expected_time:   'On time' | 'HH:mm' | 'Cancelled'
#   toc_code:        2-char train operating company code, e.g. 'GR', 'VT'

FIELDS_PER_DEPARTURE = 8

# Column definitions: (header_label, field_offset, fixed_width | None=fill_remaining)
# Exactly one column must have width=None; it expands to fill the display.
COLUMNS = [
    ('Time', 0, 45),
    ('Destination', 1, None),
    ('Plt', 2, 28),
    ('Cls', 5, 28),
    ('Op', 7, 35),
    ('Expected', 6, 70),
]

async def _draw_cell(display, x, y, w, h, text, color, align):
    textbox.draw_textbox(display, text, x, y, w, h, color=color, background=0x000000, font='small', align=align)

class TrainDisplay:
    def __init__(self, display, url, start_y):
        self.display = display
        self.url = url
        self.start_y = start_y
        self.departures = []

        self.display_width, self.display_height = self.display.get_bounds()
        self.departures_last_updated = utime.ticks_ms()

        # Pre-allocate HTTP request helper
        self._http_request = HttpRequest(url)

    CREATION_PRIORITY = 1
    def create(provider):
        y_separator = provider['config']['display'].get('y_separator', 70)
        return TrainDisplay(provider['display'], provider['config']['trains']['url'], y_separator)

    async def start(self):
        await asyncio.sleep(random.randint(5, 10))
        while True:
            await self.fetch_departures()
            await asyncio.sleep(300)  # Fetch every 5 minutes (API caches for 5m)

    def should_activate(self):
        num_departures = len(self.departures) // FIELDS_PER_DEPARTURE
        return num_departures > 0 and utime.ticks_diff(utime.ticks_ms(), self.departures_last_updated) < 600_000

    async def activate(self):
        await self.update()

    def _resolve_column_widths(self):
        return table.column_rects(0, self.display_width, [w for _, _, w in COLUMNS], min_fill_width=50)

    async def fetch_departures(self):
        try:
            async with self._http_request.get_scoped() as (reader, writer):
                self.departures = []

                # Calculate how many rows fit in the display area
                row_height = 17
                available_height = self.display_height - self.start_y - row_height
                max_rows = available_height // row_height
                max_elements = max_rows * FIELDS_PER_DEPARTURE

                async for element in load_array(reader):
                    self.departures.append(element)
                    if len(self.departures) >= max_elements:
                        writer.close()
                        await writer.wait_closed()
                        break

            # Clean up after HTTP request
            gc.collect()

            self.departures_last_updated = utime.ticks_ms()
            num_departures = len(self.departures) // FIELDS_PER_DEPARTURE
            print(f"Train data fetched: {num_departures} departures")

        except Exception as e:
            print(f"Error fetching train data: {e}")

    async def update(self):
        y_start = self.start_y
        row_height = 17
        available_height = self.display_height - self.start_y - row_height
        max_rows = available_height // row_height

        col_rects = self._resolve_column_widths()

        header_color = 0x848284
        cells = []
        for (label, _, _), (cx, cw) in zip(COLUMNS, col_rects):
            align = 'left' if cw > 50 else 'center'
            cells.append((cx, y_start, cw, row_height, _draw_cell, (label, header_color, align)))

        for row in range(max_rows):
            idx = row * FIELDS_PER_DEPARTURE
            if idx + FIELDS_PER_DEPARTURE > len(self.departures):
                break

            row_y = y_start + row_height + row * row_height
            status = self.departures[idx + 3] or 'scheduled'
            delay_minutes = self.departures[idx + 4]
            row_pen = get_color_for_train_status(status, delay_minutes)

            for (_, field_offset, _), (cx, cw) in zip(COLUMNS, col_rects):
                value = self.departures[idx + field_offset] or ''
                align = 'left' if cw > 50 else 'center'
                cells.append((cx, row_y, cw, row_height, _draw_cell, (value, row_pen, align)))

        await table.draw_cells(self.display, cells, shuffle=True)
