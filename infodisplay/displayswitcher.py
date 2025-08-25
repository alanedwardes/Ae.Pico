import asyncio

class DisplaySwitcher:
    def __init__(self, provider, services, time_ms):
        self.provider = provider
        self.services = services
        self.time_ms = time_ms
    
    def create(provider):
        config = provider['config']['switcher']
        return DisplaySwitcher(provider, config['services'], config['time_ms'])
                 
    async def start(self):
        for service in self.services:
            self.provider[service].activate(False)

        bus = self.provider.get('libraries.eventbus.EventBus') or self.provider.get('eventbus.EventBus')
        focus_queue = None
        cancel_focus_stream = None
        if bus is not None:
            focus_queue, cancel_focus_stream = bus.stream('focus.request')

        while True:           
            for service_name in self.services:
                service = self.provider[service_name]
                
                # Check if the service wants to be activated
                if hasattr(service, 'should_activate') and not service.should_activate():
                    continue
                
                service.activate(True)

                if focus_queue is None:
                    if hasattr(asyncio, 'sleep_ms'):
                        await asyncio.sleep_ms(self.time_ms)
                    else:
                        await asyncio.sleep(self.time_ms / 1000)
                else:
                    # Use wait_for to race focus request vs timeout
                    try:
                        timeout_seconds = self.time_ms / 1000
                        ev = await asyncio.wait_for(focus_queue.get(), timeout_seconds)
                        print(f"DisplaySwitcher: Focus requested, switching to {ev.data.get('instance', 'unknown')}")
                        service.activate(False)
                        
                        # Handle focus request
                        target_instance = ev.data.get('instance') if isinstance(ev.data, dict) else None
                        target_service = ev.data.get('service') if isinstance(ev.data, dict) else None
                        hold_ms = ev.data.get('hold_ms', self.time_ms) if isinstance(ev.data, dict) else self.time_ms

                        if target_instance:
                            target = target_instance
                        elif target_service:
                            target = self.provider.get(target_service)
                        else:
                            target = None
                        
                        print(f"DisplaySwitcher: target_instance={target_instance}")
                        print(f"DisplaySwitcher: target_service={target_service}")  
                        print(f"DisplaySwitcher: target={target}")

                        if target is not None:
                            print(f"DisplaySwitcher: Activating target display: {target}")
                            target.activate(True)
                            try:
                                # Show focused display for hold_ms, allow chaining
                                while True:
                                    try:
                                        hold_seconds = hold_ms / 1000
                                        ev2 = await asyncio.wait_for(focus_queue.get(), hold_seconds)
                                        target.activate(False)
                                        # Chain to next focus request
                                        target_instance = ev2.data.get('instance') if isinstance(ev2.data, dict) else None
                                        target_service = ev2.data.get('service') if isinstance(ev2.data, dict) else None
                                        hold_ms = ev2.data.get('hold_ms', self.time_ms) if isinstance(ev2.data, dict) else self.time_ms
                                        if target_instance:
                                            target = target_instance
                                        elif target_service:
                                            target = self.provider.get(target_service)
                                        else:
                                            target = None
                                        if target is None:
                                            break
                                        target.activate(True)
                                    except asyncio.TimeoutError:
                                        # Hold time expired, exit focus mode
                                        break
                            finally:
                                target.activate(False)
                        continue
                    except asyncio.TimeoutError:
                        # Normal timeout, continue rotation
                        pass
                        
                service.activate(False)

        if cancel_focus_stream is not None:
            cancel_focus_stream()
    

