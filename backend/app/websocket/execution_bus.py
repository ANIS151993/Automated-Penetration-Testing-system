from __future__ import annotations

import asyncio
import threading
from typing import AsyncIterator

TERMINAL_EVENT_TYPES = frozenset(
    {"completed", "failed", "cancelled", "timed_out"}
)

_DEFAULT_QUEUE_CAPACITY = 512


class ExecutionBus:
    """In-process fan-out of tool-execution NDJSON events.

    The gateway-validation service produces events on a worker thread
    (FastAPI runs the sync stream generator in a threadpool), while WS
    subscribers consume them on the event loop. `publish_sync` marshals
    events across the boundary via `loop.call_soon_threadsafe`.

    A single backend replica is assumed; for horizontal scale, swap this
    out for Redis pub/sub keeping the same public surface.
    """

    def __init__(self, queue_capacity: int = _DEFAULT_QUEUE_CAPACITY) -> None:
        self._subscribers: dict[str, set[asyncio.Queue[dict]]] = {}
        self._lock = threading.Lock()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._queue_capacity = queue_capacity

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Capture the event loop used for cross-thread scheduling."""
        self._loop = loop

    def subscriber_count(self, key: str) -> int:
        with self._lock:
            return len(self._subscribers.get(key, ()))

    def publish_sync(self, key: str, event: dict) -> None:
        """Fan out one event. Safe to call from a non-event-loop thread."""
        loop = self._loop
        with self._lock:
            queues = list(self._subscribers.get(key, ()))
        if not queues or loop is None or loop.is_closed():
            return
        for queue in queues:
            loop.call_soon_threadsafe(self._try_put, queue, event)

    async def publish(self, key: str, event: dict) -> None:
        """Async-native publish, for callers already on the loop."""
        with self._lock:
            queues = list(self._subscribers.get(key, ()))
        for queue in queues:
            self._try_put(queue, event)

    async def subscribe(self, key: str) -> AsyncIterator[dict]:
        """Async iterator over events for one execution key.

        Yields each event, then exits after any terminal event
        (completed / failed / cancelled / timed_out). The subscriber is
        removed when the generator is closed or garbage-collected.
        """
        queue: asyncio.Queue[dict] = asyncio.Queue(maxsize=self._queue_capacity)
        with self._lock:
            self._subscribers.setdefault(key, set()).add(queue)
        try:
            while True:
                event = await queue.get()
                yield event
                if event.get("type") in TERMINAL_EVENT_TYPES:
                    return
        finally:
            with self._lock:
                subs = self._subscribers.get(key)
                if subs is not None:
                    subs.discard(queue)
                    if not subs:
                        self._subscribers.pop(key, None)

    @staticmethod
    def _try_put(queue: asyncio.Queue[dict], event: dict) -> None:
        try:
            queue.put_nowait(event)
        except asyncio.QueueFull:
            # Slow consumer — drop the event rather than stall the producer.
            pass
