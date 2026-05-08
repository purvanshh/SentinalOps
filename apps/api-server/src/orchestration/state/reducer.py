from typing import Any


def merge_state(current: dict[str, Any], updates: dict[str, Any]) -> dict[str, Any]:
    next_state = dict(current)
    for key, value in updates.items():
        if isinstance(value, dict) and isinstance(next_state.get(key), dict):
            next_state[key] = {**next_state[key], **value}
        else:
            next_state[key] = value
    return next_state
