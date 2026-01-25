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
