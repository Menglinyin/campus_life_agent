"""Keep capacity held until actual worker completion, even after HTTP timeout."""
import asyncio
from threading import BoundedSemaphore
from .errors import BusyError, WorkTimeout

class InferenceRunner:
    def __init__(self, capacity):
        self.capacity = BoundedSemaphore(capacity)
        self.tasks = set()

    async def run(self, function, timeout):
        if not self.capacity.acquire(blocking=False):
            raise BusyError()
        def work():
            try: return function()
            finally: self.capacity.release()
        task = asyncio.create_task(asyncio.to_thread(work))
        self.tasks.add(task)
        def consume_finished(future):
            self.tasks.discard(future)
            if not future.cancelled(): future.exception()
        task.add_done_callback(consume_finished)
        try:
            return await asyncio.wait_for(asyncio.shield(task), timeout)
        except asyncio.TimeoutError as exc:
            raise WorkTimeout() from exc

    async def close(self):
        if self.tasks:
            await asyncio.gather(*tuple(self.tasks), return_exceptions=True)
