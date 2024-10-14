import asyncio

class Buttons:
    def __init__(self, polling_rate_ms = 100):
        self.bindings = []
        self.polling_rate_ms = polling_rate_ms
    
    def bind(self, pin, callback):
        self.bindings.append((pin, callback))
        
    async def start(self):
        while True:
            for pin, callback in self.bindings:
                if pin.value() == 0:
                    await callback(pin)
            await asyncio.sleep_ms(self.polling_rate_ms)
            
    async def stop(self):
        pass
