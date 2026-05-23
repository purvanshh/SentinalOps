from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Iterator

_LIVE_PROVIDER_ACCESS_ALLOWED: ContextVar[bool] = ContextVar(
    "live_provider_access_allowed",
    default=True,
)


@contextmanager
def disallow_live_providers() -> Iterator[None]:
    """Temporarily forbid live provider initialization in this execution context."""
    token = _LIVE_PROVIDER_ACCESS_ALLOWED.set(False)
    try:
        yield
    finally:
        _LIVE_PROVIDER_ACCESS_ALLOWED.reset(token)


def live_provider_access_allowed() -> bool:
    """Return whether live provider clients may be created in this context."""
    return _LIVE_PROVIDER_ACCESS_ALLOWED.get()
