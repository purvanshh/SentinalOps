from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from agents.postmortem_agent.action_items import propose_action_items
from agents.postmortem_agent.contributing_factors import evaluate_contributing_factors
from db.models.incident import Incident
from db.repositories.incident_repo import IncidentRepository
from db.repositories.postmortem_repo import PostmortemRepository


def _render_template(template: str, values: dict[str, str]) -> str:
    rendered = template
    for key, value in values.items():
        rendered = rendered.replace(f"{{{{ {key} }}}}", value)
    return rendered


def _build_timeline(executions: list[Any]) -> str:
    if not executions:
        return "- No agent executions recorded."
    lines = []
    for execution in executions:
        timestamp = execution.created_at.isoformat() if execution.created_at else "unknown"
        lines.append(f"- {timestamp}: `{execution.agent_name}` completed with status `{execution.status}`")
    return "\n".join(lines)


async def generate_postmortem(
    incident: Incident,
    *,
    db_session: AsyncSession,
) -> dict[str, Any]:
    repository = IncidentRepository(db_session)
    postmortem_repo = PostmortemRepository(db_session)
    incident_context = await repository.get_with_context(incident.id)
    if incident_context is None:
        return {}

    executions = incident_context.agent_executions
    execution_outputs = {execution.agent_name: execution.output or {} for execution in executions}
    root_cause = execution_outputs.get("rootcause_agent", {})
    risk = execution_outputs.get("risk_agent", {})
    deployment = execution_outputs.get("deployment_agent", {})
    metrics = execution_outputs.get("metrics_agent", {})
    logs = execution_outputs.get("logs_agent", {})

    contributing_factors = evaluate_contributing_factors(
        {
            "deployment": deployment,
            "metrics": metrics,
            "logs": logs,
        }
    )
    existing_prevention_items = [
        {
            "title": item.title,
            "description": item.description,
            "status": item.status,
            "completed": item.completed,
        }
        for item in await postmortem_repo.list_prevention_items()
    ]
    new_action_items = propose_action_items(
        root_cause=root_cause,
        contributing_factors=contributing_factors,
        existing_items=existing_prevention_items,
        incident_id=incident.id,
    )
    if new_action_items:
        await postmortem_repo.create_prevention_items(new_action_items)

    timeline = _build_timeline(executions)
    root_cause_summary = root_cause.get("hypotheses", [])
    top_hypothesis = None
    strongest_index = root_cause.get("strongest_hypothesis_index")
    if strongest_index is not None and root_cause_summary:
        top_hypothesis = root_cause_summary[strongest_index]

    contributing_text = "\n".join(
        f"- {factor['factor']}: {'Yes' if factor['detected'] else 'No'} — {factor['detail']}"
        for factor in contributing_factors
    )
    action_items_text = "\n".join(
        f"- {item['title']}: {item['description']}"
        for item in new_action_items
    ) or "- No new action items proposed."
    detection_metrics = (
        f"- Estimated impacted users so far: {risk.get('current_impact', {}).get('estimated_users_impacted_so_far', 0)}\n"
        f"- Blast radius mean users at risk: {risk.get('blast_radius', {}).get('users_at_risk', {}).get('mean', 0)}"
    )
    lessons_learned = (
        "Keep evidence-grounded reasoning, remediation approvals, and prevention tracking tightly coupled."
    )
    appendices = (
        f"- Evidence items captured: {len(incident_context.evidence_items)}\n"
        f"- Remediation actions tracked: {len(incident_context.remediation_actions)}"
    )

    template_path = Path("configs/development/postmortem_template.md")
    if not template_path.is_absolute():
        template_path = Path.cwd() / template_path
    template = template_path.read_text()
    content = _render_template(
        template,
        {
            "title": f"Postmortem: {incident.title}",
            "summary": incident.summary,
            "timeline": timeline,
            "root_cause_analysis": (
                top_hypothesis["hypothesis"] if top_hypothesis else "Insufficient evidence for a top hypothesis."
            ),
            "contributing_factors": contributing_text,
            "detection_metrics": detection_metrics,
            "action_items": action_items_text,
            "lessons_learned": lessons_learned,
            "appendices": appendices,
        },
    )
    existing_postmortems = await postmortem_repo.list_postmortems(incident.id)
    version = len(existing_postmortems) + 1
    row = await postmortem_repo.create_postmortem(
        incident_id=incident.id,
        title=f"Postmortem: {incident.title}",
        content=content,
        version=version,
    )
    await repository.create_agent_execution(
        incident_id=incident.id,
        agent_name="postmortem_agent",
        input_payload={"incident_id": str(incident.id)},
        output_payload={"postmortem_id": str(row.id), "version": version},
        status="completed",
    )
    return {
        "postmortem_id": str(row.id),
        "version": version,
        "title": row.title,
        "content": row.content,
    }
