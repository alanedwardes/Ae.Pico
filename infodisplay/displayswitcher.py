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
                    await asyncio.sleep(self.time_ms / 1000)
                else:
                    sleep_task = asyncio.create_task(asyncio.sleep(self.time_ms / 1000))
                    focus_task = asyncio.create_task(focus_queue.get())
                    done, pending = await asyncio.wait({sleep_task, focus_task}, return_when=asyncio.FIRST_COMPLETED)
                    for p in pending:
                        p.cancel()

                    if focus_task in done:
                        try:
                            ev = focus_task.result()
                            print(f"DisplaySwitcher: Focus requested, switching to {ev.data.get('instance', 'unknown')}")
                        except Exception:
                            ev = None

                        service.activate(False)

                        if ev is not None:
                            target_instance = ev.data.get('instance') if isinstance(ev.data, dict) else None
                            target_service = ev.data.get('service') if isinstance(ev.data, dict) else None
                            hold_ms = ev.data.get('hold_ms', self.time_ms) if isinstance(ev.data, dict) else self.time_ms

                            target = None
                            if target_instance is not None:
                                target = target_instance
                            elif target_service is not None:
                                target = self.provider.get(target_service)

                            if target is not None:
                                target.activate(True)
                                try:
                                    # While showing focused display, allow chaining of further focus requests
                                    while True:
                                        next_sleep = asyncio.create_task(asyncio.sleep(hold_ms / 1000))
                                        next_focus = asyncio.create_task(focus_queue.get())
                                        next_done, next_pending = await asyncio.wait({next_sleep, next_focus}, return_when=asyncio.FIRST_COMPLETED)
                                        for p in next_pending:
                                            p.cancel()
                                        if next_focus in next_done:
                                            try:
                                                ev2 = next_focus.result()
                                            except Exception:
                                                ev2 = None
                                            target.activate(False)
                                            if ev2 is None:
                                                break
                                            target_instance = ev2.data.get('instance') if isinstance(ev2.data, dict) else None
                                            target_service = ev2.data.get('service') if isinstance(ev2.data, dict) else None
                                            hold_ms = ev2.data.get('hold_ms', self.time_ms) if isinstance(ev2.data, dict) else self.time_ms
                                            target = target_instance or self.provider.get(target_service)
                                            if target is None:
                                                break
                                            target.activate(True)
                                        else:
                                            break
                                finally:
                                    target.activate(False)

                        # After focus handling, continue to next service
                        continue

                # Normal rotation path (no focus preemption)
                if bus is None:
                    service.activate(False)
                else:
                    # If we got here with bus, it means sleep completed
                    service.activate(False)

        if cancel_focus_stream is not None:
            cancel_focus_stream()
