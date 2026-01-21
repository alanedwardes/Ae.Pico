import rp2
import asyncio

class SkipDisplayButton:
    CREATION_PRIORITY = 1
    
    def create(provider):
        return SkipDisplayButton(provider['eventbus.EventBus'])

    def __init__(self, event_bus):
        self.event_bus = event_bus
        self.polling_rate_ms = 10
        self.debounce_ms = 250

    async def start(self):
        while True:
            if rp2.bootsel_button() == 1:
                self.event_bus.publish('focus.request')
                
                while rp2.bootsel_button() == 1:
                    await asyncio.sleep_ms(self.polling_rate_ms)
                
                await asyncio.sleep_ms(self.debounce_ms)
            
            await asyncio.sleep_ms(self.polling_rate_ms)
