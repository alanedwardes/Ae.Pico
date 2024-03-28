import utime

class DataPoint:
    # Config
    change_amount = 0
    max_time_between_updates = 0
    min_time_between_updates = 0

    # State
    __value = None
    __last_updated_value = None
    last_updated_time = None

    def __init__(self, required_change_amount = None, max_time_between_updates = 300_000, min_time_between_updates = 5_000):
        self.required_change_amount = required_change_amount
        self.max_time_between_updates = max_time_between_updates
        self.min_time_between_updates = min_time_between_updates
    
    def set_value(self, new_value):
        self.__value = new_value

    def set_value_updated(self):
        self.__last_updated_value = self.__value
        self.last_updated_time = utime.ticks_ms()

    def get_needs_update(self):
        # No value means never update
        if self.__value is None:
            return False

        # First update is required
        if self.__last_updated_value is None or self.last_updated_time is None:
            return True
        
        ms_since_last_update = utime.ticks_diff(utime.ticks_ms(), self.last_updated_time)

        # If it has been too long since the last update, send one
        if ms_since_last_update > self.max_time_between_updates:
            return True

        # If we just updated, wait a bit
        if ms_since_last_update < self.min_time_between_updates:
            return False
        
        # Check the value has changed enough
        if isinstance(self.__value, bool):
            return self.__value != self.__last_updated_value
        else:
            return abs(self.__value - self.__last_updated_value) >= self.required_change_amount
    
    def get_value(self):
        return self.__value
