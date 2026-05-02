import utime
import asyncio
import gc
import textbox
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
        """Return (x_positions, widths) lists matching COLUMNS order."""
        fixed_total = sum(w for _, _, w in COLUMNS if w is not None)
        fill_width = max(50, self.display_width - fixed_total)
        widths = [fill_width if w is None else w for _, _, w in COLUMNS]
        positions = []
        x = 0
        for w in widths:
            positions.append(x)
            x += w
        return positions, widths

    async def __draw_header_row(self, y_offset):
        header_color = 0x848284
        positions, widths = self._resolve_column_widths()
        for i, (label, _, _) in enumerate(COLUMNS):
            align = 'left' if widths[i] > 50 else 'center'
            await textbox.draw_textbox(self.display, label, positions[i], y_offset, widths[i], 20, color=header_color, font='small', align=align)

    async def __draw_departure_row(self, departure_idx, y_offset):
        idx = departure_idx * FIELDS_PER_DEPARTURE
        if idx + FIELDS_PER_DEPARTURE > len(self.departures):
            return

        status = self.departures[idx + 3] or 'scheduled'
        delay_minutes = self.departures[idx + 4]
        row_pen = get_color_for_train_status(status, delay_minutes)

        positions, widths = self._resolve_column_widths()
        for i, (_, field_offset, _) in enumerate(COLUMNS):
            value = self.departures[idx + field_offset] or ''
            align = 'left' if widths[i] > 50 else 'center'
            await textbox.draw_textbox(self.display, value, positions[i], y_offset, widths[i], 20, color=row_pen, font='small', align=align)

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

        # Clear header area
        self.display.rect(0, y_start, self.display_width, row_height, 0x000000, True)

        await self.__draw_header_row(y_start)

        # Update header
        self.display.update((0, y_start, self.display_width, row_height))

        # Allow other work to continue
        await asyncio.sleep(0)

        # Draw departure rows
        for row in range(max_rows):
            row_start = y_start + row_height + row * row_height

            # Clear this row
            self.display.rect(0, row_start, self.display_width, row_height, 0x000000, True)

            await self.__draw_departure_row(row, row_start)

            # Update just this row
            self.display.update((0, row_start, self.display_width, row_height))

            # Allow other work to continue
            await asyncio.sleep(0)
