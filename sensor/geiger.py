import utime
import datapoint

class ClickTracker:

    def __init__(self):
        self.clicks = 0
        self.started_time = utime.ticks_ms()

    def get_ms_since_start(self):
        return utime.ticks_diff(utime.ticks_ms(), self.started_time)

class Geiger:
    
    # Init: tube_cpm_ratio is specific to each geiger tube and represents the
    # value needed to convert between CPM and μSv/h (e.g. 153.8 for the tube M4011)
    def __init__(self, tube_cpm_ratio, pin, pin_trigger):
        self.datapoint = datapoint.DataPoint()
        self.click_tracker = ClickTracker()
        pin.irq(trigger=pin_trigger, handler=self.__click, hard=True)
        self.tube_cpm_ratio = tube_cpm_ratio

    # Called when the geiger tube detects ionising radiation and clicks
    # This uses a hardware interrupt so cannot do anything complex
    def __click(self, pin):
        self.click_tracker.clicks += 1
    
    # Updates the datapoint with the current μSv/h value
    # This can be called at whatever interval is desired,
    # but waiting longer periods of time will result in more
    # accurate results (e.g. 1 minute)
    def update(self):
        # Swap out the current click tracker
        previous_click_tracker = self.click_tracker
        self.click_tracker = ClickTracker()

        # Process the saturated click tracker to obtain μSv/h
        total_time = previous_click_tracker.get_ms_since_start()
        cpm_multiplier = 60_000 / total_time
        cpm = previous_click_tracker.clicks * cpm_multiplier
        self.datapoint.set_value(cpm / self.tube_cpm_ratio)

    # Get the number of ms since the last call to update()
    def get_ms_since_last_update(self):
        return self.click_tracker.get_ms_since_start()