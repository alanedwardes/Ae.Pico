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
                    async def sleep_coro():
                        if hasattr(asyncio, 'sleep_ms'):
                            await asyncio.sleep_ms(self.time_ms)
                        else:
                            await asyncio.sleep(self.time_ms / 1000)
                    
                    sleep_task = asyncio.create_task(sleep_coro())
                    focus_task = asyncio.create_task(focus_queue.get())
                    if hasattr(asyncio, 'wait'):
                        done, pending = await asyncio.wait({sleep_task, focus_task}, return_when=asyncio.FIRST_COMPLETED)
                    else:
                        # MicroPython doesn't have asyncio.wait, use alternative approach
                        done, pending = await self._wait_first_completed(sleep_task, focus_task)
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
    
    async def _wait_first_completed(self, task1, task2):
        """Alternative to asyncio.wait for MicroPython"""
        done = set()
        pending = set()
        
        try:
            # Try to use done() method if available
            while True:
                if hasattr(task1, 'done') and task1.done():
                    done.add(task1)
                    pending.add(task2)
                    break
                elif hasattr(task2, 'done') and task2.done():
                    done.add(task2)
                    pending.add(task1)
                    break
                else:
                    await asyncio.sleep_ms(1) if hasattr(asyncio, 'sleep_ms') else await asyncio.sleep(0.001)
        except AttributeError:
            # Fallback: just wait for one task to complete by trying to get results
            import sys
            try:
                await task1
                done.add(task1)
                pending.add(task2)
            except:
                done.add(task2)
                pending.add(task1)
        
        return done, pending
