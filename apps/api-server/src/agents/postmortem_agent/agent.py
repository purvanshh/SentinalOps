from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from agents.postmortem_agent.action_items import propose_action_items
from agents.postmortem_agent.contributing_factors import evaluate_contributing_factors
from agents.postmortem_agent.metrics import compute_incident_metrics
from agents.postmortem_agent.rca_narrative import build_five_whys_narrative
from agents.postmortem_agent.timeline import build_structured_timeline, render_timeline_markdown
from db.models.incident import Incident
from db.repositories.incident_repo import IncidentRepository
from db.repositories.postmortem_repo import PostmortemRepository
from retrieval.retrieval_orchestrator import RetrievalOrchestrator


def _render_template(template: str, values: dict[str, str]) -> str:
    rendered = template
    for key, value in values.items():
        rendered = rendered.replace(f"{{{{ {key} }}}}", value)
    return rendered


def _parse_alert_timestamp(raw_payload: dict[str, Any], fallback: Any) -> datetime | None:
    for key in ("startsAt", "timestamp", "alert_time"):
        value = raw_payload.get(key)
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                continue
    return fallback


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
    retrieval = RetrievalOrchestrator()
    retrieval_matches = await retrieval.search_prevention_items(
        f"{incident.title}\n{incident.summary}\n{root_cause}",
        limit=5,
    )
    existing_prevention_items.extend(
        {
            "title": item.get("title", ""),
            "description": item.get("description", ""),
            "status": item.get("status", "open"),
            "completed": False,
        }
        for item in retrieval_matches
    )
    new_action_items = propose_action_items(
        root_cause=root_cause,
        contributing_factors=contributing_factors,
        existing_items=existing_prevention_items,
        incident_id=incident.id,
    )
    if new_action_items:
        await postmortem_repo.create_prevention_items(new_action_items)

    timeline_rows = build_structured_timeline(executions, incident_context.remediation_actions)
    timeline = render_timeline_markdown(timeline_rows)
    root_cause_analysis = build_five_whys_narrative(root_cause)

    alert_time = _parse_alert_timestamp(incident.raw_payload, incident.created_at)
    incident_metrics = compute_incident_metrics(
        alert_time,
        incident_context.evidence_items,
        incident_context.remediation_actions,
        incident.updated_at,
    )
    await repository.update_incident_metrics(
        incident.id,
        first_anomaly_at=incident_metrics["first_anomaly_at"],
        mitigated_at=incident_metrics["mitigated_at"],
        resolved_at=incident_metrics["resolved_at"],
        ttd_seconds=incident_metrics["ttd_seconds"],
        ttm_seconds=incident_metrics["ttm_seconds"],
        ttr_seconds=incident_metrics["ttr_seconds"],
    )

    contributing_text = "\n".join(
        f"- {factor['factor']}: {'Yes' if factor['detected'] else 'No'} — {factor['detail']}"
        for factor in contributing_factors
    )
    action_items_text = "\n".join(
        f"- {item['title']}: {item['description']}"
        for item in new_action_items
    ) or "- No new action items proposed."
    detection_metrics = (
        f"- TTD (seconds): {incident_metrics['ttd_seconds']}\n"
        f"- TTM (seconds): {incident_metrics['ttm_seconds']}\n"
        f"- TTR (seconds): {incident_metrics['ttr_seconds']}\n"
        f"- Estimated impacted users so far: {risk.get('current_impact', {}).get('estimated_users_impacted_so_far', 0)}\n"
        f"- Blast radius mean users at risk: {risk.get('blast_radius', {}).get('users_at_risk', {}).get('mean', 0)}"
    )
    lessons_learned = (
        "Operational safety improves when evidence correlation, approval controls, and prevention tracking stay coupled."
    )
    appendices = (
        f"- Evidence items captured: {len(incident_context.evidence_items)}\n"
        f"- Remediation actions tracked: {len(incident_context.remediation_actions)}\n"
        f"- Agent executions recorded: {len(executions)}"
    )

    template_path = Path("configs/production/postmortem_template.md")
    if not template_path.is_absolute():
        template_path = Path.cwd() / template_path
    template = template_path.read_text()
    content = _render_template(
        template,
        {
            "title": f"Postmortem: {incident.title}",
            "summary": incident.summary,
            "timeline": timeline,
            "root_cause_analysis": root_cause_analysis,
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
        input_payload={"incident_id": str(incident.id), "metrics": incident_metrics},
        output_payload={"postmortem_id": str(row.id), "version": version},
        status="completed",
    )
    strongest_root_cause = root_cause.get("hypotheses", [{}])[0].get("hypothesis", "")
    await retrieval.index_resolved_incident(
        incident_id=str(incident.id),
        title=incident.title,
        summary=incident.summary,
        root_cause=strongest_root_cause,
    )
    if new_action_items:
        await retrieval.index_prevention_items(new_action_items)
    return {
        "postmortem_id": str(row.id),
        "version": version,
        "title": row.title,
        "content": row.content,
        "metrics": incident_metrics,
    }
