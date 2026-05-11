from __future__ import annotations

import time
from uuid import uuid4

import structlog

from core.resilience.operating_mode import OperatingModeManager
from memory.short_term.incident_state import IncidentStateStore
from observability.logging import bind_incident_context
from orchestration.checkpointing.checkpoint import build_langgraph_checkpointer
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
from orchestration.state.incident_state import IncidentState

logger = structlog.get_logger(__name__)


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
        workflow = StateGraph(IncidentState)
        workflow.add_node("router", router_node)
        workflow.add_node("triage", triage_node)
        workflow.add_node("dispatch_evidence", dispatch_evidence_node)
        workflow.add_node("approval_interrupt", approval_interrupt_node)
        workflow.add_node("metrics", metrics_node)
        workflow.add_node("logs", logs_node)
        workflow.add_node("deployment", deployment_node)
        workflow.add_node("root_cause_analysis", rootcause_node)
        workflow.add_node("risk", risk_node)
        workflow.add_node("remediation", remediation_node)
        workflow.add_node("approval_gate", approval_node)
        workflow.add_node("execution_actions", execution_node)
        workflow.add_node("postmortem_report", postmortem_node)

        workflow.add_edge(START, "router")
        workflow.add_conditional_edges(
            "router",
            route_after_router,
            {
                "fanout": "dispatch_evidence",
                "triage": "triage",
            },
        )
        workflow.add_conditional_edges("dispatch_evidence", fan_out_evidence, ["metrics", "logs", "deployment"])
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

    async def ainvoke(self, initial_state: dict) -> dict:
        thread_id = initial_state.get("thread_id") or str(uuid4())
        execution_id = str(uuid4())
        mode_manager = OperatingModeManager()

        # Bootstrap state - persisted BEFORE any provider interaction
        state: IncidentState = {
            "incident_id": initial_state["incident_id"],
            "thread_id": thread_id,
            "execution_id": execution_id,
            "status": "starting",
            "operating_mode": mode_manager.current_mode.value,
            "started_at": time.time(),
            "remaining_steps": int(initial_state.get("remaining_steps", 12)),
            "errors": [],
            "completed_nodes": [],
            "approved_actions": [],
            "fallback_activated": False,
        }

        bind_incident_context(incident_id=state["incident_id"], thread_id=thread_id, agent="workflow")

        # CRITICAL: Persist bootstrap state BEFORE first LLM call
        # This state survives provider failure
        await self.state_store.save_state(state["incident_id"], state)

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
            # Even if the graph fails, record the failure transparently
            logger.error(
                "workflow_execution_failed",
                incident_id=state["incident_id"],
                thread_id=thread_id,
                error=str(exc),
                operating_mode=mode_manager.current_mode.value,
            )
            failure_state = dict(state)
            failure_state["status"] = "failed"
            failure_state["errors"] = [f"Workflow execution failed: {exc}"]
            failure_state["operating_mode"] = mode_manager.current_mode.value
            await self.state_store.save_state(state["incident_id"], failure_state)
            raise

        # Persist final state with operating mode
        if isinstance(result, dict):
            result["operating_mode"] = mode_manager.current_mode.value
        await self.state_store.save_state(state["incident_id"], result)
        return result

    async def resume(self, thread_id: str, command: ResumeCommand) -> dict:
        from langgraph.types import Command

        bind_incident_context(thread_id=thread_id, agent="workflow_resume")
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
        incident_id = state.get("incident_id")
        if incident_id:
            await self.state_store.save_state(incident_id, state)
            if state.get("status") == "resolved":
                await self.state_store.delete_state(incident_id)
        return state

    async def get_state(self, thread_id: str) -> dict:
        bind_incident_context(thread_id=thread_id, agent="workflow_state")
        snapshot = await self.graph.aget_state(config=self._config(thread_id))
        values = getattr(snapshot, "values", snapshot)
        if isinstance(values, dict) and values.get("incident_id"):
            await self.state_store.save_state(values["incident_id"], values)
        return values


_GRAPH: LangGraphWorkflow | None = None


def build_main_graph() -> LangGraphWorkflow:
    global _GRAPH  # noqa: PLW0603
    if _GRAPH is None:
        _GRAPH = LangGraphWorkflow()
    return _GRAPH
