import asyncio
import threading
from typing import Optional


class ThreadSafeFlag:
    def __init__(self):
        self._event = asyncio.Event()
        self._lock = threading.Lock()
        self._waiting_task: Optional[asyncio.Task] = None

    def set(self):
        """Set the flag. If there is a task waiting on the flag, it will be scheduled to run."""
        with self._lock:
            self._event.set()

    def clear(self):
        """Clear the flag. This may be used to ensure that a possibly previously-set flag is clear before waiting for it."""
        with self._lock:
            self._event.clear()

    async def wait(self):
        """Wait for the flag to be set. If the flag is already set then it returns immediately. 
        The flag is automatically reset upon return from wait.
        
        A flag may only be waited on by a single task at a time.
        """
        with self._lock:
            if self._waiting_task is not None:
                raise RuntimeError("Flag is already being waited on by another task")
            self._waiting_task = asyncio.current_task()
        
        try:
            await self._event.wait()
            with self._lock:
                self._event.clear()
        finally:
            with self._lock:
                self._waiting_task = None
