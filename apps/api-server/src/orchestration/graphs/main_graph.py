import asyncio
from uuid import uuid4

from db.repositories.incident_repo import IncidentRepository
from db.session import SessionLocal
from orchestration.checkpointing.checkpoint import WorkflowCheckpointStore
from orchestration.interrupts.commands import ResumeCommand
from orchestration.nodes.approval_node import approval_node
from orchestration.nodes.deployment_node import deployment_node
from orchestration.nodes.execution_node import execution_node
from orchestration.nodes.logs_node import logs_node
from orchestration.nodes.metrics_node import metrics_node
from orchestration.nodes.remediation_node import remediation_node
from orchestration.nodes.risk_node import risk_node
from orchestration.nodes.rootcause_node import rootcause_node
from orchestration.nodes.router_node import router_node
from orchestration.state.reducer import merge_state


class IncidentWorkflowGraph:
    def __init__(self) -> None:
        self.checkpoints = WorkflowCheckpointStore()

    async def ainvoke(self, initial_state: dict) -> dict:
        thread_id = initial_state.get("thread_id") or str(uuid4())
        state = merge_state(initial_state, {"thread_id": thread_id, "status": "starting"})
        incident_id = state["incident_id"]

        async with SessionLocal() as session:
            repository = IncidentRepository(session)
            await repository.update_graph_thread_id(incident_id, thread_id)

        await self.checkpoints.save(
            thread_id=thread_id,
            incident_id=incident_id,
            node_name="start",
            status="running",
            state=state,
        )

        state = await self._run_node(thread_id, incident_id, "router", router_node, state)
        if state.get("router", {}).get("confidence", 1.0) < 0.6:
            return state

        metrics_state, logs_state, deployment_state = await asyncio.gather(
            self._run_parallel_node(thread_id, incident_id, "metrics", metrics_node, state),
            self._run_parallel_node(thread_id, incident_id, "logs", logs_node, state),
            self._run_parallel_node(thread_id, incident_id, "deployment", deployment_node, state),
        )
        state = merge_state(state, metrics_state)
        state = merge_state(state, logs_state)
        state = merge_state(state, deployment_state)
        await self.checkpoints.save(
            thread_id=thread_id,
            incident_id=incident_id,
            node_name="fanout_complete",
            status="running",
            state=state,
        )

        state = await self._run_node(thread_id, incident_id, "rootcause", rootcause_node, state)
        state = await self._run_node(thread_id, incident_id, "risk", risk_node, state)
        state = await self._run_node(thread_id, incident_id, "remediation", remediation_node, state)
        state = await self._run_node(thread_id, incident_id, "approval", approval_node, state)
        if state.get("status") == "awaiting_approval":
            await self.checkpoints.save(
                thread_id=thread_id,
                incident_id=incident_id,
                node_name="approval_interrupt",
                status="interrupted",
                state=state,
            )
            return state

        state = await self._run_node(thread_id, incident_id, "execution", execution_node, state)
        return state

    async def resume(self, thread_id: str, command: ResumeCommand) -> dict:
        latest = await self.checkpoints.latest(thread_id)
        if latest is None:
            raise ValueError(f"No checkpoint found for thread {thread_id}")

        state = merge_state(
            latest.state,
            {
                "approval": {
                    **latest.state.get("approval", {}),
                    "approved": command.approved,
                    "note": command.note,
                },
            },
        )
        state = await self._run_node(thread_id, str(latest.incident_id), "execution", execution_node, state)
        return state

    async def _run_node(self, thread_id: str, incident_id: str, node_name: str, node, state: dict) -> dict:
        async with SessionLocal() as session:
            updates = await node(state, session)
        next_state = merge_state(state, updates)
        await self.checkpoints.save(
            thread_id=thread_id,
            incident_id=incident_id,
            node_name=node_name,
            status=next_state.get("status", "running"),
            state=next_state,
        )
        return next_state

    async def _run_parallel_node(self, thread_id: str, incident_id: str, node_name: str, node, state: dict) -> dict:
        async with SessionLocal() as session:
            updates = await node(state, session)
        await self.checkpoints.save(
            thread_id=thread_id,
            incident_id=incident_id,
            node_name=node_name,
            status="running",
            state=merge_state(state, updates),
        )
        return updates


_GRAPH: IncidentWorkflowGraph | None = None


def build_main_graph() -> IncidentWorkflowGraph:
    global _GRAPH  # noqa: PLW0603
    if _GRAPH is None:
        _GRAPH = IncidentWorkflowGraph()
    return _GRAPH
