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
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        _drain_and_close(loop)


def _drain_and_close(loop: asyncio.AbstractEventLoop) -> None:
    try:
        pending = asyncio.all_tasks(loop)
        if pending:
            for task in pending:
                task.cancel()
            loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
    finally:
        loop.close()
        asyncio.set_event_loop(None)
