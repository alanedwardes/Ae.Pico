import asyncio

class WaitFirst:
    def __init__(self, *tasks):
        self.tasks = tasks
        self.event = asyncio.Event()
        self.winner = None
        self.result = None
        self.exception = None
        self._wrap_tasks()

    def _wrap_tasks(self):
        self.wrappers = []
        for i, task in enumerate(self.tasks):
            self.wrappers.append(asyncio.create_task(self._monitor(i, task)))

    async def _monitor(self, index, task):
        try:
            res = await task
            if self.winner is None:
                self.winner = index
                self.result = res
                self.event.set()
        except Exception as e:
            if self.winner is None:
                self.winner = index
                self.exception = e
                self.event.set()

    async def wait(self):
        await self.event.wait()
        
        # Cancel all pending tasks
        for wrapper in self.wrappers:
            wrapper.cancel()

        if self.exception:
            raise self.exception

        return self.winner, self.result


class SleepGate:
    def __init__(self, event_bus, on_sleep=None, on_wake=None):
        self._awake = asyncio.Event()
        self._awake.set()
        self._on_sleep = on_sleep
        self._on_wake = on_wake
        if event_bus is not None:
            event_bus.subscribe('system.sleep', self._sleep)
            event_bus.subscribe('system.wake', self._wake)

    def _sleep(self, ev):
        self._awake.clear()
        if self._on_sleep:
            self._on_sleep()

    def _wake(self, ev):
        self._awake.set()
        if self._on_wake:
            self._on_wake()

    async def wait_awake(self):
        await self._awake.wait()
