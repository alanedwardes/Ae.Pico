import asyncio
import asyncutils

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

    def _get_service_from_focus_event(self, ev):
        target_instance = ev.data.get('instance') if isinstance(ev.data, dict) else None
        target_service = ev.data.get('service') if isinstance(ev.data, dict) else None

        if target_instance:
            return target_instance
        elif target_service:
            return self.provider.get(target_service)
        return None

    async def start(self):
        bus = self.provider.get('eventbus.EventBus')
        focus_queue = None
        self.cancel_focus_stream = None
        if bus is not None:
            focus_queue, self.cancel_focus_stream = bus.stream('focus.request')

        self.current_index = -1
        self.manual_trigger = asyncio.Event()
        self.pause_time = 0

        while True:
            # Advance index
            if not self.services:
                 await asyncio.sleep(1)
                 continue

            if self.pause_time > 0:
                print(f"DisplaySwitcher: Paused for {self.pause_time}s")
                try:
                    await asyncio.wait_for(self.manual_trigger.wait(), self.pause_time)
                except asyncio.TimeoutError:
                    pass # Timer expired, remove pause
                
                self.pause_time = 0
                self.manual_trigger.clear()
                # If manually triggered during pause, we might want to skip or just resume normal flow
                # For now, let's just resume normal flow which means moving to next

            self.current_index = (self.current_index + 1) % len(self.services)
            service_name = self.services[self.current_index]
            service = self.provider[service_name]
            
            # Check if the service wants to be activated
            if hasattr(service, 'should_activate') and not service.should_activate():
                continue

            # Cancel any previous active task and start new one
            await self._cancel_active_task()
            self.active_task = asyncio.create_task(service.activate())

            try:
                if focus_queue is None:
                    # Normal wait or manual interrupt
                    timeout = self.time_ms / 1000
                    await asyncio.wait_for(self.manual_trigger.wait(), timeout)
                    self.manual_trigger.clear()
                else:
                    # Wait for focus request, timeout (next slide), or manual trigger
                    # This requires composite waiting. simplest is to poll or use first_completed
                    # but wait_for is for a single future.
                    # Let's use a task for the timeout/manual trigger
                    
                    async def wait_condition():
                        timeout = self.time_ms / 1000
                        try:
                            await asyncio.wait_for(self.manual_trigger.wait(), timeout)
                        except asyncio.TimeoutError:
                            pass
                        self.manual_trigger.clear()
                    
                    async def wait_condition():
                        timeout = self.time_ms / 1000
                        try:
                            await asyncio.wait_for(self.manual_trigger.wait(), timeout)
                        except asyncio.TimeoutError:
                            pass
                        self.manual_trigger.clear()

                    waiter = asyncutils.WaitFirst(wait_condition(), focus_queue.get())
                    winner, result = await waiter.wait()

                    if winner == 1:
                        # Focus requested
                        ev = result
                        
                        target = self._get_service_from_focus_event(ev)
                        print(f"DisplaySwitcher: Focus requested, switching to {target} (cancelling {self.active_task})")
                        await self._cancel_active_task()
                        
                        # Handle focus request
                        hold_ms = ev.data.get('hold_ms', self.time_ms) if isinstance(ev.data, dict) else self.time_ms

                        if target is not None:
                            print(f"DisplaySwitcher: Activating target display: {target}")
                            self.active_task = asyncio.create_task(target.activate())
                            try:
                                # Show focused display for hold_ms, allow chaining
                                while True:
                                    try:
                                        hold_seconds = hold_ms / 1000
                                        # We also need to allow manual trigger to break out of focus? maybe not for now.
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
                # Should be caught inside wait_condition usually
                pass

    def next(self):
        """Skip to the next display immediately."""
        self.manual_trigger.set()

    def prev(self):
        """Go back to the previous display immediately."""
        # Current index will be incremented at start of loop, so we want:
        # (current - 2) + 1 = current - 1
        # If we are currently showing index 5.
        # Loop start: increment to 6.
        # We want to show 4.
        # So set to 3.
        # 3 + 1 = 4.
        # So set to current - 2.
        self.current_index = (self.current_index - 2) % len(self.services)
        self.manual_trigger.set()

    def pause(self, seconds):
        """Pause on the current display for a specific time."""
        # Set pause time. We need to trigger loop to recycle, but we need to stay on current index.
        # Loop increments. So set to current - 1.
        self.current_index = (self.current_index - 1) % len(self.services)
        self.pause_time = seconds
        self.manual_trigger.set()


    

