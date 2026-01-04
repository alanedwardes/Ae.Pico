import asyncio

class DisplaySwitcher:
    def __init__(self, provider, services, time_ms):
        self.provider = provider
        self.services = services
        self.time_ms = time_ms
        self.active_task = None  # Track the currently active display task
    
    def create(provider):
        config = provider['config']['switcher']
        return DisplaySwitcher(provider, config['services'], config['time_ms'])

    async def _cancel_active_task(self):
        """Cancel and clean up the active display task."""
        if self.active_task is not None:
            self.active_task.cancel()
            try:
                await self.active_task
            except asyncio.CancelledError:
                pass
            except Exception as e:
                print("DisplaySwitcher - exception when cancelling active task: %s" % type(e))
            finally:
                self.active_task = None

    async def start(self):
        bus = self.provider.get('eventbus.EventBus')
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

                # Cancel any previous active task and start new one
                await self._cancel_active_task()
                self.active_task = asyncio.create_task(service.activate())

                if focus_queue is None:
                    await asyncio.sleep(self.time_ms / 1000)
                else:
                    # Use wait_for to race focus request vs timeout
                    try:
                        timeout_seconds = self.time_ms / 1000
                        ev = await asyncio.wait_for(focus_queue.get(), timeout_seconds)
                        print(f"DisplaySwitcher: Focus requested, switching to {ev.data.get('instance', 'unknown')}")
                        await self._cancel_active_task()
                        
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
                            self.active_task = asyncio.create_task(target.activate())
                            try:
                                # Show focused display for hold_ms, allow chaining
                                while True:
                                    try:
                                        hold_seconds = hold_ms / 1000
                                        ev2 = await asyncio.wait_for(focus_queue.get(), hold_seconds)
                                        await self._cancel_active_task()
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
                                        self.active_task = asyncio.create_task(target.activate())
                                    except asyncio.TimeoutError:
                                        # Hold time expired, exit focus mode
                                        break
                            finally:
                                await self._cancel_active_task()
                        continue
                    except asyncio.TimeoutError:
                        # Normal timeout, continue rotation
                        pass

        if cancel_focus_stream is not None:
            cancel_focus_stream()
    

