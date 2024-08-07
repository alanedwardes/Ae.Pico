import utime
import datapoint

class ClickTracker:

    def __init__(self):
        self.clicks = 0
        self.started_time = utime.ticks_ms()

    def get_ms_since_start(self):
        return utime.ticks_diff(utime.ticks_ms(), self.started_time)
    
    # To derive the μSv/h value, multiply this value by tube's
    # specific CPM ratio (e.g. 153.8 for the tube M4011)
    def get_clicks_per_minute(self):
        total_time = self.get_ms_since_start()

        if total_time == 0:
            return 0
        
        cpm_multiplier = 60_000 / total_time
        return self.clicks * cpm_multiplier

class Geiger:
    
    # Init: tube_cpm_ratio is specific to each geiger tube and represents the
    # value needed to convert between CPM and μSv/h (e.g. 153.8 for the tube M4011)
    def __init__(self, tube_cpm_ratio, pin, pin_trigger, time_between_updates, required_change_amount = None):
        self.datapoint = datapoint.DataPoint(required_change_amount)
        self.click_tracker = ClickTracker()
        pin.irq(trigger=pin_trigger, handler=self.__click, hard=True)
        self.tube_cpm_ratio = tube_cpm_ratio
        self.time_between_updates = time_between_updates

    # Called when the geiger tube detects ionising radiation and clicks
    # This uses a hardware interrupt so cannot do anything complex
    def __click(self, pin):
        self.click_tracker.clicks += 1
    
    # Updates the datapoint with the current μSv/h value when time_between_updates elapses
    def update(self):
        # Don't update more frequently than configured
        if self.click_tracker.get_ms_since_start() < self.time_between_updates:
            return None

        # Swap out the current click tracker
        previous_click_tracker = self.click_tracker
        self.click_tracker = ClickTracker()

        # Process the saturated click tracker to obtain μSv/h
        self.datapoint.set_value(previous_click_tracker.get_clicks_per_minute() / self.tube_cpm_ratio)
        
        # Return the previous click tracker
        return previous_click_tracker
