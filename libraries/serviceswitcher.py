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
            for service_name in self.services:
                service = self.provider[service_name]
                
                # Check if the service wants to be activated
                if hasattr(service, 'should_activate') and not service.should_activate():
                    continue
                
                service.activate(True)
                await asyncio.sleep(self.time_ms / 1000)
                service.activate(False)
