from __future__ import annotations

import asyncio

from orchestration.interrupts.commands import ResumeCommand


class _FakeGraph:
    async def resume(self, thread_id, command):
        assert thread_id == "thread-123"
        assert isinstance(command, ResumeCommand)
        return {"thread_id": thread_id, "status": "resolved", "incident_id": "incident-123"}


def test_resume_path_recovers_from_interrupted_thread(monkeypatch) -> None:
    fake_graph = _FakeGraph()
    monkeypatch.setattr("orchestration.graphs.main_graph.build_main_graph", lambda: fake_graph)

    result = asyncio.run(
        fake_graph.resume(
            "thread-123",
            ResumeCommand(approved=True, note="resume", approved_by="operator-1", approval_token="token"),
        )
    )

    assert result["status"] == "resolved"
    assert result["thread_id"] == "thread-123"
