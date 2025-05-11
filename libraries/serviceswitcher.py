import asyncio

class ServiceSwitcher:
    def __init__(self, provider, services, time_ms):
        self.provider = provider
        self.services = services
        self.time_ms = time_ms
    
    def create(provider):
        config = provider['config']['switcher']
        return ServiceSwitcher(provider, config['services'], config['time_ms'])
                 
    async def start(self):
        for service in self.services:
            self.provider[service].activate(False)

        while True:
            for service in self.services:
                self.provider[service].activate(True)
                await asyncio.sleep_ms(self.time_ms)
                self.provider[service].activate(False)
