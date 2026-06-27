import asyncio
import threading
from typing import Optional

class ThreadSafeFlag:
    def __init__(self):
        self._event = asyncio.Event()
        self._lock = threading.Lock()
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def set(self):
        """Set the flag from any thread. Uses call_soon_threadsafe when called from outside the event loop."""
        with self._lock:
            loop = self._loop
        if loop is not None:
            loop.call_soon_threadsafe(self._event.set)
        else:
            self._event.set()

    def clear(self):
        """Clear the flag. Must be called from the event loop thread."""
        self._event.clear()

    async def wait(self):
        """Wait for the flag to be set. If the flag is already set then it returns immediately.
        The flag is automatically reset upon return from wait.
        """
        with self._lock:
            self._loop = asyncio.get_event_loop()
        await self._event.wait()
        self._event.clear()

asyncio.ThreadSafeFlag = ThreadSafeFlag