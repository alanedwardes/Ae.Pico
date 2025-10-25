import utime
import asyncio
import machine

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

class HassGeiger:
    def __init__(self, hass, pin, friendly_name, sensor, cpm_ratio, update_time_ms):
        self.click_tracker = ClickTracker()
        self.hass = hass
        self.pin = machine.Pin(pin, machine.Pin.IN, machine.Pin.PULL_DOWN)
        self.pin.irq(self.interrupt, machine.Pin.IRQ_RISING)
        self.friendly_name = friendly_name
        self.sensor = sensor
        self.cpm_ratio = cpm_ratio
        self.update_time_ms = update_time_ms

    def interrupt(self, pin):
        self.click_tracker.clicks += 1

    CREATION_PRIORITY = 1
    def create(provider):
        config = provider['config']['geiger']
        return HassGeiger(provider['hass.Hass'], config['pin'], config['friendly_name'], config['sensor'], config['cpm_ratio'], config['update_time_ms'])
    
    async def start(self):
        while True:
            await asyncio.sleep_ms(self.update_time_ms)
            
            old_tracker = self.click_tracker
            self.click_tracker = ClickTracker()
            cpm = old_tracker.get_clicks_per_minute()
            await self.hass.send_update(cpm / self.cpm_ratio, "μSv/h", None, self.friendly_name, self.sensor)
            await self.hass.send_update(cpm, "CPM", None, self.friendly_name + " CPM", self.sensor + "_cpm")
