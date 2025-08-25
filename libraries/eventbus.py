import asyncio
import utime


class Event:
	def __init__(self, name, data=None, ts_ms=None):
		self.name = name
		self.data = data
		self.ts_ms = ts_ms if ts_ms is not None else utime.ticks_ms()


class EventBus:
	CREATION_PRIORITY = 0

	def create(provider):
		return EventBus()

	def __init__(self):
		self._next_token = 1
		self._subs = {}
		self._tokens = {}
		self._queues = {}

	async def start(self):
		await asyncio.Event().wait()

	def subscribe(self, event, callback):
		token = self._next_token
		self._next_token += 1
		self._subs.setdefault(event, set()).add((token, callback))
		self._tokens[token] = event
		return token

	def unsubscribe(self, token):
		event = self._tokens.pop(token, None)
		if event is None:
			return
		subs = self._subs.get(event)
		if not subs:
			return
		for item in list(subs):
			if item[0] == token:
				subs.remove(item)
		if not subs:
			self._subs.pop(event, None)

	def publish(self, event, data=None):
		ev = Event(event, data)
		for _, cb in list(self._subs.get(event, ())):
			asyncio.create_task(self._run_cb(cb, ev))
		for q in list(self._queues.get(event, ())):
			try:
				q.put_nowait(ev)
			except:
				pass

	async def _run_cb(self, cb, ev):
		try:
			res = cb(ev)
			if hasattr(res, "__await__"):
				await res
		except Exception as e:
			try:
				print("EventBus callback error:", type(e).__name__, str(e))
			except:
				pass

	async def wait(self, event, predicate=None):
		q, cancel = self.stream(event, maxsize=1)
		try:
			while True:
				ev = await q.get()
				if predicate is None or predicate(ev):
					return ev
		finally:
			cancel()

	def stream(self, event, maxsize=0):
		q = asyncio.Queue(maxsize=maxsize)
		self._queues.setdefault(event, set()).add(q)
		def cancel():
			qs = self._queues.get(event)
			if not qs:
				return
			qs.discard(q)
			if not qs:
				self._queues.pop(event, None)
		return q, cancel


