import hashlib
import json
from typing import Any

_CACHE: dict[str, dict[str, Any]] = {}


def cache_key(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def get_cached(payload: dict[str, Any]) -> dict[str, Any] | None:
    return _CACHE.get(cache_key(payload))


def set_cached(payload: dict[str, Any], value: dict[str, Any]) -> None:
    _CACHE[cache_key(payload)] = value
