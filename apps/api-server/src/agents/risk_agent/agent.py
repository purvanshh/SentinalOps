from __future__ import annotations

from agents.risk_agent.action_risk import score_remediation_action
from agents.risk_agent.blast_radius import compute_blast_radius
from agents.risk_agent.data_fetcher import build_runtime_inputs
from agents.risk_agent.schemas import RiskAssessment
from db.models.incident import Incident
from db.repositories.incident_repo import IncidentRepository
from db.repositories.risk_repo import RiskRepository
from sqlalchemy.ext.asyncio import AsyncSession


def _default_remediation_history() -> list[dict]:
    return [
        {
            "action_name": "rollback deployment",
            "category": "deployment_rollback",
            "success": True,
            "execution_time_seconds": 90.0,
            "severity_on_failure": 0.2,
        },
        {
            "action_name": "restart payment-api",
            "category": "service_restart",
            "success": False,
            "execution_time_seconds": 180.0,
            "severity_on_failure": 0.7,
        },
        {
            "action_name": "scale payment-api",
            "category": "scaling",
            "success": True,
            "execution_time_seconds": 75.0,
            "severity_on_failure": 0.3,
        },
    ]


def _candidate_actions(root_cause_execution: dict | None) -> list[str]:
    payload = root_cause_execution or {}
    contributing_causes = " ".join(payload.get("contributing_causes", []))
    hypotheses = payload.get("hypotheses", [])
    if not hypotheses and not contributing_causes:
        return ["restart payment-api"]
    top = hypotheses[payload.get("strongest_hypothesis_index", 0)] if hypotheses else {}
    text = (
        f"{top.get('hypothesis', '')} " f"{top.get('causal_chain', '')} " f"{contributing_causes}"
    ).lower()
    actions: list[str] = []
    if "deploy" in text or "regression" in text:
        actions.append("rollback deployment")
    if "pool" in text or "latency" in text:
        actions.append("restart payment-api")
    if "postgres" in text or "database" in text:
        actions.append("restart payment-api")
    actions.append("scale payment-api")
    return list(dict.fromkeys(actions))


def _severity_factor(incident_type: str | None, historical_incidents: list[dict]) -> float:
    if not incident_type:
        return 0.2
    matching = [row for row in historical_incidents if row.get("incident_type") == incident_type]
    if not matching:
        return 0.2
    return float(matching[0].get("severity_factor", "0.2"))


async def assess_risk(
    incident: Incident,
    *,
    db_session: AsyncSession,
) -> RiskAssessment:
    repository = IncidentRepository(db_session)
    risk_repository = RiskRepository(db_session)
    service = incident.raw_payload.get("labels", {}).get("service", "payment-api")
    runtime_inputs = await build_runtime_inputs(service)
    topology = runtime_inputs["topology"]
    traffic = runtime_inputs["traffic"]
    historical_incidents = runtime_inputs["historical_incidents"]

    rootcause_execution = next(
        (
            execution.output
            for execution in incident.agent_executions
            if execution.agent_name == "rootcause_agent"
        ),
        None,
    )
    severity_factor = _severity_factor(incident.incident_type, historical_incidents)
    blast_radius = compute_blast_radius(service, topology, traffic, severity_factor=severity_factor)
    current_rps = float(traffic.get(service, {}).get("rps", 100.0))
    current_impact = {
        "error_rate": round(min(severity_factor + 0.03, 0.95), 4),
        "estimated_users_impacted_so_far": int(current_rps * severity_factor * 10),
        "trend": "increasing" if severity_factor >= 0.2 else "stable",
    }

    history_rows = await risk_repository.seed_remediation_history(_default_remediation_history())
    serialized_history = [
        {
            "action_name": row.action_name,
            "category": row.category,
            "success": row.success,
            "execution_time_seconds": row.execution_time_seconds,
            "severity_on_failure": row.severity_on_failure,
        }
        for row in history_rows
    ]

    remediation_risks = []
    for action in _candidate_actions(rootcause_execution):
        remediation_risks.append(
            {"action": action, **score_remediation_action(action, serialized_history)}
        )

    result = RiskAssessment.model_validate(
        {
            "current_impact": current_impact,
            "blast_radius": blast_radius,
            "remediation_risks": remediation_risks,
        }
    )
    await repository.create_agent_execution(
        incident_id=incident.id,
        agent_name="risk_agent",
        input_payload={
            "service": service,
            "severity_factor": severity_factor,
            "root_cause": rootcause_execution,
            "traffic": traffic.get(service, {}),
        },
        output_payload=result.model_dump(mode="json"),
        status="completed",
    )
    return result
