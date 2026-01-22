try:
    from collections import namedtuple
except ImportError:
    # Fallback for MicroPython without collections
    def namedtuple(name, fields):
        class NamedTuple:
            def __init__(self, *args):
                for field, value in zip(fields.split(), args):
                    setattr(self, field, value)
        return NamedTuple

import utime
import asyncio
import gc
import textbox
import random
from httpstream import HttpRequest
from flatjson import parse_flat_json_array

# Define Departure named tuple for memory efficiency
Departure = namedtuple('Departure', 'scheduled_time expected_time destination platform train_class cancelled delayed')

def format_time_to_hhmm(time_str):
    """Convert datetime string to HH:MM format."""
    if not time_str:
        return ''
    
    # Handle "On time" or similar text
    if isinstance(time_str, str) and not ':' in time_str:
        return time_str
    
    # Try to extract HH:MM from various formats
    # Format could be: "14:30:00", "2024-01-15T14:30:00", "14:30", etc.
    time_str = str(time_str)
    
    # Look for HH:MM pattern
    if 'T' in time_str:
        # ISO format: extract time part after T
        time_part = time_str.split('T')[1]
        if '+' in time_part:
            time_part = time_part.split('+')[0]
        if 'Z' in time_part:
            time_part = time_part.replace('Z', '')
        time_str = time_part
    
    # Extract HH:MM (first 5 characters if format is HH:MM:SS)
    if ':' in time_str:
        parts = time_str.split(':')
        if len(parts) >= 2:
            return f"{parts[0]:0>2}:{parts[1]:0>2}"
    
    return time_str[:5] if len(time_str) >= 5 else time_str

def parse_time_to_minutes(time_str):
    """Parse HH:MM time string to minutes since midnight. Returns None if invalid."""
    if not time_str or time_str == 'TBC' or ':' not in str(time_str):
        return None
    try:
        parts = str(time_str).split(':')
        if len(parts) >= 2:
            hours = int(parts[0])
            minutes = int(parts[1])
            return hours * 60 + minutes
    except (ValueError, IndexError):
        pass
    return None

def calculate_delay_minutes(std_str, atd_str):
    """Calculate delay in minutes between scheduled (std) and actual (atd) times."""
    std_minutes = parse_time_to_minutes(std_str)
    atd_minutes = parse_time_to_minutes(atd_str)
    
    if std_minutes is None or atd_minutes is None:
        return None
    
    delay = atd_minutes - std_minutes
    # Handle day rollover (e.g., scheduled 23:50, actual 00:10 next day)
    if delay < -720:  # More than 12 hours negative, assume next day
        delay += 1440
    elif delay > 720:  # More than 12 hours positive, assume previous day
        delay -= 1440
    
    return delay if delay > 0 else 0

def get_color_for_train_status(std_str, atd_str, cancelled):
    """Get color for train status based on cancellation and delay."""
    if cancelled:
        return 0xF346  # Red for cancelled
    
    if std_str == 'TBC' or atd_str == 'TBC':
        return 0x8410  # Gray for TBC
    
    delay_minutes = calculate_delay_minutes(std_str, atd_str)
    
    if delay_minutes is None:
        return 0x8410  # Grey for unknown/on time
    
    if delay_minutes == 0:
        return 0xFFFF  # White for on time
    elif delay_minutes <= 5:
        return 0xFEC0  # Yellow for minor delay (1-5 min)
    elif delay_minutes <= 15:
        return 0xFDA2  # Orange-yellow for moderate delay (6-15 min)
    elif delay_minutes <= 30:
        return 0xF346  # Orange-red for significant delay (16-30 min)
    else:
        return 0xF800  # Red for major delay (>30 min)

class TrainDisplay:
    def __init__(self, display, url):
        self.display = display
        self.url = url
        self.departures = []

        self.display_width, self.display_height = self.display.get_bounds()
        self.departures_last_updated = utime.ticks_ms()

        # Pre-allocate HTTP request helper
        self._http_request = HttpRequest(url)
   
    CREATION_PRIORITY = 1
    def create(provider):
        config = provider['config']['trains']
        return TrainDisplay(provider['display'], config['url'])
    
    async def start(self):
        await asyncio.sleep(random.randint(5, 10))
        while True:
            await self.fetch_departures()
            await asyncio.sleep(300)  # Fetch every 5 minutes (API caches for 5m)

    def should_activate(self):
        # Data format: [std, station, platform, class, atd, cancelled, delayed, ...]
        num_departures = len(self.departures) // 7
        return num_departures > 0 and utime.ticks_diff(utime.ticks_ms(), self.departures_last_updated) < 600_000

    async def activate(self):
        await self.update()

    def __draw_header_row(self, y_offset):
        """Draw header row with column labels."""
        header_color = 0x8410  # Grey for header
        
        # Define column widths (same as departure rows)
        time_width = 50
        destination_width = 160
        platform_width = 30
        train_class_width = 30
        expected_width = 50
        
        # Draw header labels
        textbox.draw_textbox(self.display, 'Time', 0, y_offset, time_width, 20, color=header_color, font='small')
        textbox.draw_textbox(self.display, 'Destination', time_width, y_offset, destination_width, 20, color=header_color, font='small', align='left')
        textbox.draw_textbox(self.display, 'Plt', time_width + destination_width, y_offset, platform_width, 20, color=header_color, font='small')
        textbox.draw_textbox(self.display, 'Cls', time_width + destination_width + platform_width, y_offset, train_class_width, 20, color=header_color, font='small')
        textbox.draw_textbox(self.display, 'Exp', time_width + destination_width + platform_width + train_class_width, y_offset, expected_width, 20, color=header_color, font='small')
    
    def __draw_departure_row(self, departure_idx, y_offset):
        # Data format: [std, station, platform, class, atd, cancelled, delayed, ...]
        idx = departure_idx * 7
        if idx > len(self.departures) -1:
            return
        
        scheduled = self.departures[idx] or 'TBC'
        destination = self.departures[idx + 1] or ''
        platform = self.departures[idx + 2] or '-'
        train_class = self.departures[idx + 3] or '-'
        expected = self.departures[idx + 4] or 'TBC'
        cancelled = self.departures[idx + 5]
        delayed = self.departures[idx + 6]

        row_pen = get_color_for_train_status(scheduled, expected, cancelled)
        
        # Define column widths and positions
        time_width = 50
        destination_width = 160
        platform_width = 30
        train_class_width = 30
        expected_width = 50
        
        # Draw each column using textbox
        textbox.draw_textbox(self.display, scheduled, 0, y_offset, time_width, 20, color=row_pen, font='small')
        textbox.draw_textbox(self.display, destination, time_width, y_offset, destination_width, 20, color=row_pen, font='small', align='left')
        textbox.draw_textbox(self.display, platform, time_width + destination_width, y_offset, platform_width, 20, color=row_pen, font='small')
        textbox.draw_textbox(self.display, train_class, time_width + destination_width + platform_width, y_offset, train_class_width, 20, color=row_pen, font='small')
        textbox.draw_textbox(self.display, expected, time_width + destination_width + platform_width + train_class_width, y_offset, expected_width, 20, color=row_pen, font='small')
    
    async def fetch_departures(self):
        try:
            # Use unified HTTP request helper
            async with self._http_request.get_scoped() as (reader, writer):
                # Stream parse JSON array without buffering entire response
                # Format: [std, station, platform, class, atd, std, station, platform, class, atd, ...]
                # Store as flat array: [std_formatted, station, platform, class, atd_formatted, cancelled, delayed, ...]
                self.departures = []
                element_buffer = []

                async for element in parse_flat_json_array(reader):
                    element_buffer.append(element)

                    # Process in groups of 5 (std, station, platform, class, atd)
                    if len(element_buffer) == 5:
                        std = element_buffer[0]
                        station = element_buffer[1]
                        platform = element_buffer[2]
                        train_class = element_buffer[3]
                        atd = element_buffer[4]

                        # Format times to HH:MM
                        std_formatted = format_time_to_hhmm(std)
                        atd_formatted = format_time_to_hhmm(atd)

                        # Determine if cancelled or delayed
                        cancelled = False
                        delayed = False

                        # If atd is empty or "On time", check for delays
                        if atd_formatted and atd_formatted != std_formatted and atd_formatted != "On time":
                            delayed = True

                        # Convert empty strings to display values
                        scheduled_time_display = std_formatted if std_formatted else ''
                        expected_time_display = atd_formatted if atd_formatted else scheduled_time_display
                        destination_display = station if station else ''
                        platform_display = platform if platform else ''
                        train_class_display = train_class if train_class else ''

                        # Append as flat array: std, station, platform, class, atd, cancelled, delayed
                        self.departures.append(scheduled_time_display)
                        self.departures.append(destination_display)
                        self.departures.append(platform_display)
                        self.departures.append(train_class_display)
                        self.departures.append(expected_time_display)
                        self.departures.append(cancelled)
                        self.departures.append(delayed)

                        element_buffer = []

            # Clean up after HTTP request
            import gc
            gc.collect()

            self.departures_last_updated = utime.ticks_ms()
            # Data format: [std, station, platform, class, atd, cancelled, delayed, ...]
            num_departures = len(self.departures) // 7
            print(f"Train data fetched: {num_departures} departures")

        except Exception as e:
            print(f"Error fetching train data: {e}")
    
    def get_departures(self):
        # Return number of departures for backward compatibility
        return len(self.departures) // 7

    async def update(self):
        y_start = 70
        row_height = 17

        # Clear header area
        self.display.rect(0, y_start, self.display_width, row_height, 0x0000, True)

        self.__draw_header_row(y_start)

        # Allow other work to continue
        await asyncio.sleep(0)

        # Draw departure rows
        for row in range(9):
            row_start = y_start + row_height + row * row_height

            # Clear this row
            self.display.rect(0, row_start, self.display_width, row_height, 0x0000, True)

            self.__draw_departure_row(row, row_start)

            # Allow other work to continue
            await asyncio.sleep(0)
