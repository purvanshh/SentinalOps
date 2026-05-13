from __future__ import annotations

import threading
import time
from uuid import uuid4

import structlog
from core.resilience.operating_mode import OperatingModeManager
from db.repositories.incident_repo import IncidentRepository
from db.session import SessionLocal
from memory.short_term.incident_state import IncidentStateStore
from observability.logging import bind_incident_context
from orchestration.checkpointing.checkpoint import (
    WorkflowCheckpointStore,
    build_langgraph_checkpointer,
)
from orchestration.interrupts.commands import ResumeCommand
from orchestration.nodes.approval_node import approval_node
from orchestration.nodes.deployment_node import deployment_node
from orchestration.nodes.execution_node import execution_node
from orchestration.nodes.logs_node import logs_node
from orchestration.nodes.metrics_node import metrics_node
from orchestration.nodes.postmortem_node import postmortem_node
from orchestration.nodes.remediation_node import remediation_node
from orchestration.nodes.risk_node import risk_node
from orchestration.nodes.rootcause_node import rootcause_node
from orchestration.nodes.router_node import router_node
from orchestration.state.incident_state import IncidentState, append_unique
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)
_GRAPH_LOCK = threading.Lock()


def route_after_router(state: IncidentState) -> str:
    if state.get("remaining_steps", 0) <= 0:
        return "triage"
    if state.get("status") == "needs_triage":
        return "triage"
    return "fanout"


def fan_out_evidence(state: IncidentState):
    from langgraph.constants import Send

    return [
        Send("metrics", state),
        Send("logs", state),
        Send("deployment", state),
    ]


async def triage_node(state: IncidentState) -> dict:
    return {
        "status": "needs_triage",
        "errors": ["Incident classification confidence below automation threshold"],
        "completed_nodes": ["triage"],
    }


async def dispatch_evidence_node(state: IncidentState) -> dict:
    return {"completed_nodes": ["dispatch_evidence"]}


def route_after_approval(state: IncidentState) -> str:
    if state.get("status") == "awaiting_approval":
        return "approval_interrupt"
    return "execution_actions"


async def approval_interrupt_node(state: IncidentState) -> dict:
    return state


class LangGraphWorkflow:
    def __init__(self) -> None:
        from langgraph.graph import END, START, StateGraph

        self.state_store = IncidentStateStore()
        self._checkpoint_store = WorkflowCheckpointStore()
        workflow = StateGraph(IncidentState)
        workflow.add_node("router", self._checkpointed_node("router", router_node))
        workflow.add_node("triage", self._checkpointed_node("triage", triage_node))
        workflow.add_node(
            "dispatch_evidence",
            self._checkpointed_node("dispatch_evidence", dispatch_evidence_node),
        )
        workflow.add_node(
            "approval_interrupt",
            self._checkpointed_node("approval_interrupt", approval_interrupt_node),
        )
        workflow.add_node("metrics", self._checkpointed_node("metrics", metrics_node))
        workflow.add_node("logs", self._checkpointed_node("logs", logs_node))
        workflow.add_node("deployment", self._checkpointed_node("deployment", deployment_node))
        workflow.add_node(
            "root_cause_analysis",
            self._checkpointed_node("root_cause_analysis", rootcause_node),
        )
        workflow.add_node("risk", self._checkpointed_node("risk", risk_node))
        workflow.add_node("remediation", self._checkpointed_node("remediation", remediation_node))
        workflow.add_node("approval_gate", self._checkpointed_node("approval_gate", approval_node))
        workflow.add_node(
            "execution_actions",
            self._checkpointed_node("execution_actions", execution_node),
        )
        workflow.add_node(
            "postmortem_report",
            self._checkpointed_node("postmortem_report", postmortem_node),
        )

        workflow.add_edge(START, "router")
        workflow.add_conditional_edges(
            "router",
            route_after_router,
            {
                "fanout": "dispatch_evidence",
                "triage": "triage",
            },
        )
        workflow.add_conditional_edges(
            "dispatch_evidence", fan_out_evidence, ["metrics", "logs", "deployment"]
        )
        workflow.add_edge("metrics", "root_cause_analysis")
        workflow.add_edge("logs", "root_cause_analysis")
        workflow.add_edge("deployment", "root_cause_analysis")
        workflow.add_edge("root_cause_analysis", "risk")
        workflow.add_edge("risk", "remediation")
        workflow.add_edge("remediation", "approval_gate")
        workflow.add_conditional_edges(
            "approval_gate",
            route_after_approval,
            {
                "approval_interrupt": "approval_interrupt",
                "execution_actions": "execution_actions",
            },
        )
        workflow.add_edge("approval_interrupt", "execution_actions")
        workflow.add_edge("triage", END)
        workflow.add_edge("execution_actions", "postmortem_report")
        workflow.add_edge("postmortem_report", END)

        self.graph = workflow.compile(
            checkpointer=build_langgraph_checkpointer(),
            interrupt_before=["approval_interrupt"],
        )

    @staticmethod
    def _config(thread_id: str) -> dict:
        return {"configurable": {"thread_id": thread_id}}

    def _merge_state_for_checkpoint(self, state: dict, updates: dict) -> dict:
        merged = dict(state)
        for key, value in updates.items():
            if key in {"errors", "completed_nodes"}:
                merged[key] = append_unique(list(merged.get(key, [])), value)
            else:
                merged[key] = value
        return merged

    def _checkpointed_node(self, node_name: str, node_func):
        async def wrapped(state: IncidentState) -> dict:
            try:
                update = await node_func(state)
            except Exception as exc:
                failure_state = dict(state)
                failure_state["failure_reason"] = str(exc)
                failure_state["last_successful_step"] = state.get(
                    "last_successful_step", "bootstrap"
                )
                failure_state["graph_status"] = "failed"
                failure_state["errors"] = append_unique(
                    list(state.get("errors", [])),
                    [f"{node_name} failed: {exc}"],
                )
                await self._persist_runtime_snapshot(
                    incident_id=state["incident_id"],
                    thread_id=state["thread_id"],
                    node_name=node_name,
                    status="failed",
                    state=failure_state,
                )
                raise

            merged = self._merge_state_for_checkpoint(state, update)
            merged["current_node"] = node_name
            await self._persist_runtime_snapshot(
                incident_id=state["incident_id"],
                thread_id=state["thread_id"],
                node_name=node_name,
                status=merged.get("status", "running"),
                state=merged,
            )
            return update

        return wrapped

    async def _persist_runtime_snapshot(
        self,
        *,
        incident_id: str,
        thread_id: str,
        node_name: str,
        status: str,
        state: dict,
    ) -> None:
        await self.state_store.save_state(incident_id, state)
        try:
            await self._checkpoint_store.save(
                thread_id=thread_id,
                incident_id=incident_id,
                node_name=node_name,
                status=status,
                state=dict(state),
            )
        except Exception as exc:
            logger.warning("checkpoint_save_failed", node=node_name, error=str(exc))

    async def _recover_state(self, incident_id: str, thread_id: str | None = None) -> dict | None:
        recover_state = getattr(self._checkpoint_store, "recover_state", None)
        checkpoint_state = None
        if callable(recover_state):
            checkpoint_state = await recover_state(
                thread_id=thread_id,
                incident_id=incident_id,
            )
        if checkpoint_state:
            return checkpoint_state
        load_state = getattr(self.state_store, "load_state", None)
        if callable(load_state):
            return await load_state(incident_id)
        return None

    async def _continue_from_state(self, state: dict) -> dict:
        current = dict(state)
        completed = set(current.get("completed_nodes", []))

        async def apply(node_name: str, node_func) -> None:
            nonlocal current, completed
            if node_name in completed:
                return
            update = await node_func(current)
            current = self._merge_state_for_checkpoint(current, update)
            completed = set(current.get("completed_nodes", []))
            current.setdefault("thread_id", state["thread_id"])
            current.setdefault("incident_id", state["incident_id"])
            await self._persist_runtime_snapshot(
                incident_id=current["incident_id"],
                thread_id=current["thread_id"],
                node_name=node_name,
                status=current.get("status", "running"),
                state=current,
            )

        if current.get("status") == "awaiting_approval":
            return current
        terminal = {"completed", "completed_degraded", "failed", "observe_only"}
        if current.get("graph_status") in terminal:
            return current

        await apply("dispatch_evidence", dispatch_evidence_node)
        await apply("metrics", metrics_node)
        await apply("logs", logs_node)
        await apply("deployment", deployment_node)
        await apply("root_cause_analysis", rootcause_node)
        await apply("risk", risk_node)
        await apply("remediation", remediation_node)
        await apply("approval_gate", approval_node)

        if current.get("status") == "awaiting_approval":
            return current

        await apply("execution_actions", execution_node)
        await apply("postmortem_report", postmortem_node)
        return current

    async def ainvoke(self, initial_state: dict) -> dict:
        recovered = await self._recover_state(
            initial_state["incident_id"], initial_state.get("thread_id")
        )
        terminal_statuses = {"completed", "completed_degraded", "observe_only", "failed"}
        if recovered:
            if recovered.get("graph_status") in terminal_statuses:
                return recovered
            if recovered.get("status") == "awaiting_approval":
                return recovered
            if recovered.get("completed_nodes"):
                recovered["retry_count"] = int(recovered.get("retry_count", 0)) + 1
                recovered["graph_status"] = "recovering"
                return await self._continue_from_state(recovered)

        thread_id = initial_state.get("thread_id") or str(uuid4())
        execution_id = str(uuid4())
        mode_manager = OperatingModeManager()

        state: IncidentState = {
            "incident_id": initial_state["incident_id"],
            "thread_id": thread_id,
            "execution_id": execution_id,
            "status": "starting",
            "graph_status": "bootstrapped",
            "operating_mode": mode_manager.current_mode.value,
            "started_at": time.time(),
            "classification_started_at": time.time(),
            "remaining_steps": int(initial_state.get("remaining_steps", 12)),
            "retry_count": 0,
            "provider_attempts": [],
            "last_successful_step": "bootstrap",
            "failure_reason": None,
            "errors": [],
            "completed_nodes": [],
            "approved_actions": [],
            "fallback_activated": False,
            "degraded_mode_activation": {},
        }

        bind_incident_context(
            incident_id=state["incident_id"], thread_id=thread_id, agent="workflow"
        )

        # Persist bootstrap state to both Redis and PostgreSQL before any LLM call.
        # The PostgreSQL checkpoint is the durable recovery anchor — it survives
        # Redis eviction and worker restarts.
        await self.state_store.save_state(state["incident_id"], state)
        try:
            async with SessionLocal() as session:
                await self._persist_bootstrap_runtime(session, state)
        except Exception as exc:
            logger.warning("bootstrap_runtime_persist_failed", error=str(exc))
        try:
            await self._checkpoint_store.save(
                thread_id=thread_id,
                incident_id=state["incident_id"],
                node_name="bootstrap",
                status="started",
                state=dict(state),
            )
        except Exception as exc:
            logger.warning("checkpoint_save_failed", node="bootstrap", error=str(exc))

        logger.info(
            "workflow_bootstrap_persisted",
            incident_id=state["incident_id"],
            thread_id=thread_id,
            execution_id=execution_id,
            operating_mode=state["operating_mode"],
        )

        try:
            result = await self.graph.ainvoke(state, config=self._config(thread_id))
        except Exception as exc:
            logger.error(
                "workflow_execution_failed",
                incident_id=state["incident_id"],
                thread_id=thread_id,
                error=str(exc),
                operating_mode=mode_manager.current_mode.value,
            )
            failure_state = dict(state)
            failure_state["status"] = "failed"
            failure_state["graph_status"] = "failed"
            failure_state["errors"] = [f"Workflow execution failed: {exc}"]
            failure_state["failure_reason"] = str(exc)
            failure_state["operating_mode"] = mode_manager.current_mode.value
            await self.state_store.save_state(state["incident_id"], failure_state)
            try:
                async with SessionLocal() as session:
                    await self._persist_failure_runtime(session, failure_state)
            except Exception as db_exc:
                logger.warning("failure_runtime_persist_failed", error=str(db_exc))
            try:
                await self._checkpoint_store.save(
                    thread_id=thread_id,
                    incident_id=state["incident_id"],
                    node_name="failure",
                    status="failed",
                    state=failure_state,
                )
            except Exception as cp_exc:
                logger.warning("checkpoint_save_failed", node="failure", error=str(cp_exc))
            raise

        if isinstance(result, dict):
            result["operating_mode"] = mode_manager.current_mode.value
            result.setdefault("graph_status", "completed")
        await self.state_store.save_state(state["incident_id"], result)
        try:
            async with SessionLocal() as session:
                await self._persist_final_runtime(session, result)
        except Exception as exc:
            logger.warning("final_runtime_persist_failed", error=str(exc))

        # Persist final state to PostgreSQL for durability
        try:
            await self._checkpoint_store.save(
                thread_id=thread_id,
                incident_id=state["incident_id"],
                node_name="completed",
                status=(
                    result.get("status", "completed") if isinstance(result, dict) else "completed"
                ),
                state=dict(result) if isinstance(result, dict) else {},
            )
        except Exception as exc:
            logger.warning("checkpoint_save_failed", node="completed", error=str(exc))

        return result

    async def resume(self, thread_id: str, command: ResumeCommand) -> dict:
        bind_incident_context(thread_id=thread_id, agent="workflow_resume")
        try:
            from langgraph.types import Command

            state = await self.graph.ainvoke(
                Command(
                    resume={
                        "approval": {
                            "approved": command.approved,
                            "note": command.note,
                            "approved_by": command.approved_by,
                            "approval_token": command.approval_token,
                        }
                    }
                ),
                config=self._config(thread_id),
            )
        except Exception as exc:
            logger.warning("graph_resume_fallback", thread_id=thread_id, error=str(exc))
            async with SessionLocal() as session:
                incident = await IncidentRepository(session).get_by_thread_id(thread_id)
            if incident is None:
                raise
            recovered = await self._recover_state(str(incident.id), thread_id)
            if recovered is None:
                raise
            recovered["approval"] = {
                "approved": command.approved,
                "note": command.note,
                "approved_by": command.approved_by,
                "approval_token": command.approval_token,
            }
            recovered["status"] = "ready_for_execution" if command.approved else "approval_rejected"
            recovered["graph_status"] = "resuming"
            state = await self._continue_from_state(recovered)
        incident_id = state.get("incident_id")
        if incident_id:
            await self.state_store.save_state(incident_id, state)
            try:
                await self._checkpoint_store.save(
                    thread_id=thread_id,
                    incident_id=incident_id,
                    node_name="resumed",
                    status=state.get("status", "resumed"),
                    state=dict(state),
                )
            except Exception as exc:
                logger.warning("checkpoint_save_failed", node="resumed", error=str(exc))
            if state.get("status") == "resolved":
                await self.state_store.delete_state(incident_id)
        return state

    async def get_state(self, thread_id: str) -> dict:
        bind_incident_context(thread_id=thread_id, agent="workflow_state")
        snapshot = await self.graph.aget_state(config=self._config(thread_id))
        values = getattr(snapshot, "values", snapshot)
        if not values:
            values = await self._checkpoint_store.recover_state(thread_id=thread_id) or {}
        if isinstance(values, dict) and values.get("incident_id"):
            await self.state_store.save_state(values["incident_id"], values)
        return values

    async def _persist_bootstrap_runtime(self, session: AsyncSession, state: IncidentState) -> None:
        await IncidentRepository(session).update_runtime_status(
            state["incident_id"],
            status="starting",
            graph_thread_id=state["thread_id"],
            classification_rationale=(
                f"Workflow bootstrapped with execution_id={state['execution_id']} "
                f"mode={state['operating_mode']}"
            ),
        )

    async def _persist_failure_runtime(self, session: AsyncSession, state: IncidentState) -> None:
        await IncidentRepository(session).update_runtime_status(
            state["incident_id"],
            status=state.get("status", "failed"),
            graph_thread_id=state.get("thread_id"),
            classification_rationale=state.get("failure_reason"),
        )

    async def _persist_final_runtime(self, session: AsyncSession, state: dict) -> None:
        await IncidentRepository(session).update_runtime_status(
            state["incident_id"],
            status=state.get("status"),
            graph_thread_id=state.get("thread_id"),
        )


_GRAPH: LangGraphWorkflow | None = None


def build_main_graph() -> LangGraphWorkflow:
    global _GRAPH  # noqa: PLW0603
    if _GRAPH is None:
        with _GRAPH_LOCK:
            if _GRAPH is None:
                _GRAPH = LangGraphWorkflow()
    return _GRAPH


def reset_graph() -> None:
    """Force reconstruction of the graph singleton.

    Called after worker restart or when the checkpointer's connection pool
    becomes stale. Ensures a fresh MemorySaver/checkpointer is used.
    """
    global _GRAPH  # noqa: PLW0603
    _GRAPH = None
