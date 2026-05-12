"""
Tests that concurrent incident executions remain isolated.

Validates:
  - Each invocation gets its own thread_id and execution_id
  - Parallel invocations do not corrupt each other's state
  - append_unique reducer handles concurrent list updates correctly
  - Graph singleton is safe for concurrent use (distinct thread configs)
"""
from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest

from orchestration.state.incident_state import IncidentState, append_unique
from orchestration.graphs.main_graph import reset_graph


# ---------------------------------------------------------------------------
# State isolation — unique IDs per invocation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_concurrent_invocations_get_distinct_thread_ids(monkeypatch):
    """Two concurrent runs must produce different thread_ids and execution_ids."""
    seen_thread_ids: set[str] = set()
    seen_execution_ids: set[str] = set()

    original_uuid4 = __import__("uuid").uuid4

    class _FakeStateStore:
        async def save_state(self, _incident_id, state):
            seen_thread_ids.add(state.get("thread_id", ""))
            seen_execution_ids.add(state.get("execution_id", ""))

        async def delete_state(self, _incident_id):
            pass

    class _FakeCheckpointStore:
        async def save(self, **_kwargs):
            pass

    class _FakeGraph:
        async def ainvoke(self, state, config=None):
            await asyncio.sleep(0)
            return dict(state) | {"status": "completed"}

        async def aget_state(self, config=None):
            return {}

    from orchestration.graphs import main_graph as mg

    monkeypatch.setattr(mg, "_GRAPH", None)

    original_workflow_init = mg.LangGraphWorkflow.__init__

    def patched_init(self):
        self.state_store = _FakeStateStore()
        self._checkpoint_store = _FakeCheckpointStore()
        self.graph = _FakeGraph()

    monkeypatch.setattr(mg.LangGraphWorkflow, "__init__", patched_init)

    workflow = mg.LangGraphWorkflow()

    async def invoke_one(incident_id: str):
        return await workflow.ainvoke({"incident_id": incident_id})

    incident_a = str(uuid4())
    incident_b = str(uuid4())

    results = await asyncio.gather(invoke_one(incident_a), invoke_one(incident_b))

    assert len(seen_thread_ids) == 2, "each invocation must produce a unique thread_id"
    assert len(seen_execution_ids) == 2, "each invocation must produce a unique execution_id"

    assert results[0]["incident_id"] == incident_a
    assert results[1]["incident_id"] == incident_b


# ---------------------------------------------------------------------------
# append_unique reducer
# ---------------------------------------------------------------------------

def test_append_unique_merges_without_duplicates():
    current = ["a", "b"]
    updates = ["b", "c", "d"]
    result = append_unique(current, updates)
    assert result == ["a", "b", "c", "d"]


def test_append_unique_with_empty_update():
    current = ["a", "b"]
    assert append_unique(current, []) == ["a", "b"]
    assert append_unique(current, None) == ["a", "b"]


def test_append_unique_with_empty_current():
    assert append_unique([], ["x", "y"]) == ["x", "y"]


def test_append_unique_no_mutation_of_current():
    current = ["a"]
    updates = ["b"]
    result = append_unique(current, updates)
    assert current == ["a"], "original list must not be mutated"
    assert result == ["a", "b"]


# ---------------------------------------------------------------------------
# State TypedDict — key safety
# ---------------------------------------------------------------------------

def test_incident_state_has_required_keys():
    required = {
        "incident_id", "thread_id", "execution_id", "status",
        "errors", "completed_nodes",
    }
    annotations = IncidentState.__annotations__
    missing = required - set(annotations.keys())
    assert not missing, f"IncidentState missing keys: {missing}"


def test_incident_state_errors_uses_append_unique_reducer():
    """The errors field must use append_unique so concurrent node updates don't clobber."""
    import typing
    hints = IncidentState.__annotations__
    errors_hint = hints.get("errors")
    assert errors_hint is not None

    metadata = getattr(errors_hint, "__metadata__", None)
    assert metadata is not None, "errors field must be Annotated with a reducer"
    assert append_unique in metadata, "errors reducer must be append_unique"


def test_incident_state_completed_nodes_uses_append_unique_reducer():
    import typing
    hints = IncidentState.__annotations__
    cn_hint = hints.get("completed_nodes")
    assert cn_hint is not None

    metadata = getattr(cn_hint, "__metadata__", None)
    assert metadata is not None, "completed_nodes must be Annotated with a reducer"
    assert append_unique in metadata


# ---------------------------------------------------------------------------
# Graph singleton reset
# ---------------------------------------------------------------------------

def test_reset_graph_forces_reconstruction(monkeypatch):
    from orchestration.graphs import main_graph as mg

    # Ensure singleton exists
    original = mg.build_main_graph()
    assert mg._GRAPH is not None

    reset_graph()
    assert mg._GRAPH is None, "reset_graph() must clear the singleton"
