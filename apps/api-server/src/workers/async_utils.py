"""
Safe asyncio bridge for Celery sync-to-async task execution.

Celery workers run in synchronous threads. asyncio.run() is the standard way
to call async code from sync context, but it fails in two scenarios:
  1. After a task retry, the previous loop may be closed and still set as the
     thread-local loop, causing RuntimeError('Event loop is closed').
  2. When a nested loop already exists (Jupyter, certain testing harnesses),
     asyncio.run() raises RuntimeError('This event loop is already running').

run_async() fixes both by always constructing a private loop per call,
running to completion, draining any pending tasks, and closing cleanly.
"""
from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from typing import Any, TypeVar

T = TypeVar("T")


def run_async(coro: Coroutine[Any, Any, T]) -> T:
    """Run *coro* in a fresh, isolated event loop.

    Safe for repeated calls in the same thread (including Celery retries) and
    safe when the calling thread already has a closed or stale loop set.
    """
    _ensure_no_running_loop(coro)
    _clear_stale_thread_loop()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        _drain_and_close(loop)


def _ensure_no_running_loop(coro: Coroutine[Any, Any, T]) -> None:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return

    coro.close()
    raise RuntimeError(
        "run_async() cannot be called while an event loop is already running; "
        "await the coroutine directly instead."
    )


def _clear_stale_thread_loop() -> None:
    try:
        existing_loop = asyncio.get_event_loop_policy().get_event_loop()
    except RuntimeError:
        return

    if existing_loop.is_closed():
        asyncio.set_event_loop(None)


def _drain_and_close(loop: asyncio.AbstractEventLoop) -> None:
    try:
        pending = asyncio.all_tasks(loop)
        if pending:
            for task in pending:
                task.cancel()
            loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        loop.run_until_complete(loop.shutdown_asyncgens())
        loop.run_until_complete(loop.shutdown_default_executor())
    finally:
        loop.close()
        asyncio.set_event_loop(None)
