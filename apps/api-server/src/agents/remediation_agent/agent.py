from agents.remediation_agent.output_schema import RemediationPlan
from db.models.incident import Incident
from db.repositories.incident_repo import IncidentRepository
from sqlalchemy.ext.asyncio import AsyncSession


async def build_remediation_plan(
    incident: Incident,
    *,
    db_session: AsyncSession,
) -> RemediationPlan:
    risk_execution = (
        next(
            (
                execution.output
                for execution in incident.agent_executions
                if execution.agent_name == "risk_agent"
            ),
            None,
        )
        or {}
    )
    remediation_risks = risk_execution.get("remediation_risks", [])

    steps = []
    for index, action in enumerate(remediation_risks, start=1):
        steps.append(
            {
                "action": action["action"],
                "requires_approval": True,
                "rationale": action.get("recommendation", "review manually"),
                "verification_metric": "latency_p99",
                "priority": index,
            }
        )

    if not steps:
        steps.append(
            {
                "action": "restart payment-api",
                "requires_approval": True,
                "rationale": "Fallback remediation when risk analysis is unavailable.",
                "verification_metric": "latency_p99",
                "priority": 1,
            }
        )

    result = RemediationPlan.model_validate(
        {
            "summary": "Proposed low-risk remediation steps based on the current risk analysis.",
            "steps": steps,
            "verify_after_execution": True,
        }
    )

    repository = IncidentRepository(db_session)
    await repository.create_agent_execution(
        incident_id=incident.id,
        agent_name="remediation_agent",
        input_payload={"risk_assessment": risk_execution},
        output_payload=result.model_dump(mode="json"),
        status="completed",
    )
    return result
