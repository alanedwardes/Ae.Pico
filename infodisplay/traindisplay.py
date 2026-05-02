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

# API format: flat array, 7 fields per departure
# [scheduled_time, destination, platform, status, delay_minutes, train_class, expected_time, ...]
#   scheduled_time:  HH:mm UK local string
#   destination:     display name string
#   platform:        platform string, 'TBC' if suppressed, '-' if unallocated
#   status:          'scheduled' | 'late' | 'early' | 'cancelled'
#   delay_minutes:   null when on-time/cancelled; positive=int late, negative=int early
#   train_class:     class string, '-' if unknown
#   expected_time:   'On time' | 'HH:mm' | 'Cancelled'

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
        num_departures = len(self.departures) // 7
        return num_departures > 0 and utime.ticks_diff(utime.ticks_ms(), self.departures_last_updated) < 600_000

    async def activate(self):
        await self.update()

    async def __draw_header_row(self, y_offset):
        """Draw header row with column labels."""
        header_color = 0x848284  # Grey for header

        # Define column widths
        time_width = 50
        platform_width = 30
        train_class_width = 30
        expected_width = 50

        # Calculate destination width dynamically
        destination_width = self.display_width - (time_width + platform_width + train_class_width + expected_width)

        # Ensure minimum width
        if destination_width < 50:
             destination_width = 50

        # Draw header labels
        await textbox.draw_textbox(self.display, 'Time', 0, y_offset, time_width, 20, color=header_color, font='small')
        await textbox.draw_textbox(self.display, 'Destination', time_width, y_offset, destination_width, 20, color=header_color, font='small', align='left')
        await textbox.draw_textbox(self.display, 'Plt', time_width + destination_width, y_offset, platform_width, 20, color=header_color, font='small')
        await textbox.draw_textbox(self.display, 'Cls', time_width + destination_width + platform_width, y_offset, train_class_width, 20, color=header_color, font='small')
        await textbox.draw_textbox(self.display, 'Exp', time_width + destination_width + platform_width + train_class_width, y_offset, expected_width, 20, color=header_color, font='small')

    async def __draw_departure_row(self, departure_idx, y_offset):
        idx = departure_idx * 7
        if idx + 6 > len(self.departures) - 1:
            return

        scheduled = self.departures[idx] or ''
        destination = self.departures[idx + 1] or ''
        platform = self.departures[idx + 2]
        status = self.departures[idx + 3] or 'scheduled'
        delay_minutes = self.departures[idx + 4]
        train_class = self.departures[idx + 5]
        expected = self.departures[idx + 6]

        row_pen = get_color_for_train_status(status, delay_minutes)

        # Define column widths and positions
        time_width = 50
        platform_width = 30
        train_class_width = 30
        expected_width = 50

        # Calculate destination width dynamically
        destination_width = self.display_width - (time_width + platform_width + train_class_width + expected_width)

        # Ensure minimum width
        if destination_width < 50:
             destination_width = 50

        # Draw each column using textbox
        await textbox.draw_textbox(self.display, scheduled, 0, y_offset, time_width, 20, color=row_pen, font='small')
        await textbox.draw_textbox(self.display, destination, time_width, y_offset, destination_width, 20, color=row_pen, font='small', align='left')
        await textbox.draw_textbox(self.display, platform, time_width + destination_width, y_offset, platform_width, 20, color=row_pen, font='small')
        await textbox.draw_textbox(self.display, train_class, time_width + destination_width + platform_width, y_offset, train_class_width, 20, color=row_pen, font='small')
        await textbox.draw_textbox(self.display, expected, time_width + destination_width + platform_width + train_class_width, y_offset, expected_width, 20, color=row_pen, font='small')

    async def fetch_departures(self):
        try:
            async with self._http_request.get_scoped() as (reader, writer):
                self.departures = []

                # Calculate how many rows fit in the display area
                row_height = 17
                available_height = self.display_height - self.start_y - row_height
                max_rows = available_height // row_height
                max_elements = max_rows * 7

                async for element in load_array(reader):
                    self.departures.append(element)
                    if len(self.departures) >= max_elements:
                        writer.close()
                        await writer.wait_closed()
                        break

            # Clean up after HTTP request
            gc.collect()

            self.departures_last_updated = utime.ticks_ms()
            # Data format: [scheduled, destination, platform, status, delay_minutes, train_class, ...]
            num_departures = len(self.departures) // 7
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
