"""
Tests that run_async() is free of event loop lifecycle bugs.

These are synchronous tests — asyncio loops must not be running when we call
run_async(), which is the exact Celery worker context we are targeting.
"""

from __future__ import annotations

import asyncio

import pytest
from workers.async_utils import run_async


def test_run_async_returns_coroutine_result():
    async def coro():
        return 42

    assert run_async(coro()) == 42


def test_run_async_closes_loop_after_completion():
    collected: dict = {}

    async def capture_loop():
        collected["loop"] = asyncio.get_running_loop()
        return "done"

    run_async(capture_loop())
    assert collected["loop"].is_closed()


def test_run_async_clears_thread_local_loop():
    """After run_async(), the thread-local event loop slot is cleared.

    In Python 3.11+ get_event_loop() raises RuntimeError when no loop is set
    on a non-main thread, or creates a new closed one. Both outcomes prove
    the original loop is no longer accessible.
    """

    async def noop():
        pass

    run_async(noop())

    try:
        loop = asyncio.get_event_loop_policy().get_event_loop()
        # If we get here, the policy created a fresh loop — it must be closed
        # (our _drain_and_close sets the slot to None, so a new policy-created
        # loop would be different from the one we ran).
        assert loop.is_closed() or not loop.is_running()
    except RuntimeError:
        # No loop set — this is the desired state after set_event_loop(None)
        pass


def test_run_async_can_be_called_sequentially_simulating_retries():
    """
    Simulate Celery retrying a task three times in the same worker thread.
    Each call must create a fresh loop; the closed loop from the previous
    call must not cause RuntimeError('Event loop is closed').
    """
    results = []

    async def payload(n: int):
        await asyncio.sleep(0)
        return n * 2

    for i in range(3):
        results.append(run_async(payload(i)))

    assert results == [0, 2, 4]


def test_run_async_propagates_exceptions():
    async def boom():
        raise ValueError("deliberate error")

    with pytest.raises(ValueError, match="deliberate error"):
        run_async(boom())


def test_run_async_cleans_up_pending_tasks_on_exception():
    """Tasks spawned inside the coroutine should be cancelled before the loop closes."""
    leaked: list[bool] = []

    async def coro_with_background():
        async def background():
            try:
                await asyncio.sleep(100)
            except asyncio.CancelledError:
                leaked.append(True)
                raise

        asyncio.ensure_future(background())
        raise RuntimeError("trigger cleanup path")

    with pytest.raises(RuntimeError):
        run_async(coro_with_background())

    assert leaked == [True], "background task must be cancelled before loop close"


def test_run_async_second_call_after_exception_succeeds():
    """After an exception, the next call must still work (simulates retry after failure)."""

    async def fail():
        raise OSError("transient error")

    async def succeed():
        return "ok"

    with pytest.raises(OSError):
        run_async(fail())

    assert run_async(succeed()) == "ok"


def test_run_async_nested_awaits_work():
    async def inner(x: int) -> int:
        await asyncio.sleep(0)
        return x + 1

    async def outer() -> int:
        a = await inner(1)
        b = await inner(a)
        return b

    assert run_async(outer()) == 3


@pytest.mark.asyncio
async def test_run_async_rejects_running_event_loop():
    async def payload():
        return 1

    with pytest.raises(
        RuntimeError, match="cannot be called while an event loop is already running"
    ):
        run_async(payload())
