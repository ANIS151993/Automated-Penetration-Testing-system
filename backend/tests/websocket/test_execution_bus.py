from __future__ import annotations

import asyncio
import threading

import pytest

from app.websocket.execution_bus import ExecutionBus


@pytest.mark.asyncio
async def test_two_subscribers_both_receive_events():
    bus = ExecutionBus()
    bus.bind_loop(asyncio.get_running_loop())

    async def drain(key: str) -> list[dict]:
        collected: list[dict] = []
        async for event in bus.subscribe(key):
            collected.append(event)
        return collected

    task_a = asyncio.create_task(drain("exec-1"))
    task_b = asyncio.create_task(drain("exec-1"))
    await asyncio.sleep(0)  # let both subscribers register

    await bus.publish("exec-1", {"type": "started"})
    await bus.publish("exec-1", {"type": "stdout", "line": "22/tcp open"})
    await bus.publish("exec-1", {"type": "completed", "status": "completed"})

    results = await asyncio.wait_for(asyncio.gather(task_a, task_b), timeout=1)
    for events in results:
        assert [e["type"] for e in events] == ["started", "stdout", "completed"]


@pytest.mark.asyncio
async def test_subscriber_receives_only_its_key():
    bus = ExecutionBus()
    bus.bind_loop(asyncio.get_running_loop())

    task = asyncio.create_task(_collect(bus, "exec-A"))
    await asyncio.sleep(0)

    await bus.publish("exec-B", {"type": "stdout", "line": "other scan"})
    await bus.publish("exec-A", {"type": "started"})
    await bus.publish("exec-A", {"type": "completed"})

    events = await asyncio.wait_for(task, timeout=1)
    assert [e["type"] for e in events] == ["started", "completed"]


@pytest.mark.asyncio
async def test_publish_sync_from_worker_thread():
    bus = ExecutionBus()
    bus.bind_loop(asyncio.get_running_loop())
    task = asyncio.create_task(_collect(bus, "exec-T"))
    await asyncio.sleep(0)

    def producer() -> None:
        bus.publish_sync("exec-T", {"type": "started"})
        bus.publish_sync("exec-T", {"type": "stdout", "line": "one"})
        bus.publish_sync("exec-T", {"type": "completed", "status": "completed"})

    thread = threading.Thread(target=producer)
    thread.start()
    thread.join()

    events = await asyncio.wait_for(task, timeout=1)
    assert [e["type"] for e in events] == ["started", "stdout", "completed"]


@pytest.mark.asyncio
async def test_subscriber_removed_after_terminal_event():
    bus = ExecutionBus()
    bus.bind_loop(asyncio.get_running_loop())
    task = asyncio.create_task(_collect(bus, "exec-C"))
    await asyncio.sleep(0)
    assert bus.subscriber_count("exec-C") == 1

    await bus.publish("exec-C", {"type": "completed"})
    await asyncio.wait_for(task, timeout=1)
    assert bus.subscriber_count("exec-C") == 0


async def _collect(bus: ExecutionBus, key: str) -> list[dict]:
    return [event async for event in bus.subscribe(key)]
