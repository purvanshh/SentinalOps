from __future__ import annotations

import asyncio
from dataclasses import dataclass

from orchestration.checkpointing.checkpoint import WorkflowCheckpointStore


@dataclass
class _Checkpoint:
    state: dict
    state_hash: str


class _ScalarResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class _ExecuteResult:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return _ScalarResult(self._rows)


class _FakeSession:
    def __init__(self, rows):
        self._rows = rows

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    async def execute(self, _statement):
        return _ExecuteResult(self._rows)


def test_latest_checkpoint_skips_corrupt_state(monkeypatch) -> None:
    store = WorkflowCheckpointStore()
    valid_state = {"incident_id": "abc", "status": "classified"}
    valid_hash = store._state_hash(valid_state)
    rows = [
        _Checkpoint(state={"incident_id": "abc", "status": "corrupt"}, state_hash="bad-hash"),
        _Checkpoint(state=valid_state, state_hash=valid_hash),
    ]

    monkeypatch.setattr(
        "orchestration.checkpointing.checkpoint.SessionLocal",
        lambda: _FakeSession(rows),
    )

    result = asyncio.run(store.latest("thread-123"))

    assert result is rows[1]
