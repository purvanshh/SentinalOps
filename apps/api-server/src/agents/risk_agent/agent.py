import csv
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from agents.risk_agent.action_risk import score_remediation_action
from agents.risk_agent.blast_radius import compute_blast_radius, load_traffic_snapshots
from agents.risk_agent.schemas import RiskAssessment
from db.models.incident import Incident
from db.repositories.incident_repo import IncidentRepository
from db.repositories.risk_repo import RiskRepository
from orchestration.state.topology import load_topology


def _load_historical_incidents(path: str | None = None) -> list[dict]:
    dataset_path = Path(path or "simulation/datasets/historical_incidents.csv")
    if not dataset_path.is_absolute():
        dataset_path = Path.cwd() / dataset_path
    if not dataset_path.exists():
        return []
    with dataset_path.open() as handle:
        return list(csv.DictReader(handle))


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
            "action_name": "rollback deployment",
            "category": "deployment_rollback",
            "success": True,
            "execution_time_seconds": 120.0,
            "severity_on_failure": 0.2,
        },
        {
            "action_name": "restart service",
            "category": "service_restart",
            "success": False,
            "execution_time_seconds": 180.0,
            "severity_on_failure": 0.7,
        },
        {
            "action_name": "restart service",
            "category": "service_restart",
            "success": True,
            "execution_time_seconds": 150.0,
            "severity_on_failure": 0.7,
        },
    ]


def _candidate_actions(root_cause_execution: dict | None) -> list[str]:
    payload = root_cause_execution or {}
    hypotheses = payload.get("hypotheses", [])
    if not hypotheses:
        return ["restart payment-api"]
    top_index = payload.get("strongest_hypothesis_index")
    if top_index is None or top_index >= len(hypotheses):
        top_index = 0
    top = hypotheses[top_index]
    text = f"{top.get('hypothesis', '')} {top.get('causal_chain', '')}".lower()
    actions: list[str] = []
    if "deploy" in text or "regression" in text:
        actions.append("rollback deployment")
    if "pool" in text or "latency" in text:
        actions.append("restart payment-api")
    actions.append("scale payment-api")
    deduped: list[str] = []
    for action in actions:
        if action not in deduped:
            deduped.append(action)
    return deduped


async def assess_risk(
    incident: Incident,
    *,
    db_session: AsyncSession,
) -> RiskAssessment:
    repository = IncidentRepository(db_session)
    risk_repository = RiskRepository(db_session)
    topology = load_topology()
    traffic = load_traffic_snapshots()
    historical_incidents = _load_historical_incidents()
    service = incident.raw_payload.get("labels", {}).get("service", "payment-api")
    rootcause_execution = next(
        (execution.output for execution in incident.agent_executions if execution.agent_name == "rootcause_agent"),
        None,
    )
    severity_factor = 0.2
    if historical_incidents:
        matching = [
            row
            for row in historical_incidents
            if row.get("incident_type") == (incident.incident_type or "")
        ]
        if matching:
            severity_factor = float(matching[0].get("severity_factor", "0.2"))

    blast_radius = compute_blast_radius(service, topology, traffic, severity_factor=severity_factor)
    current_rps = int(traffic.get(service, {}).get("rps", 100))
    current_impact = {
        "error_rate": min(severity_factor + 0.03, 0.95),
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
        scored = score_remediation_action(action, serialized_history)
        remediation_risks.append(
            {
                "action": action,
                **scored,
            }
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
        },
        output_payload=result.model_dump(mode="json"),
        status="completed",
    )
    return result
