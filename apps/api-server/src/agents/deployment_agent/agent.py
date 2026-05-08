from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from agents.base_agent import agent_loop
from agents.deployment_agent.output_schema import DeploymentSummary
from agents.deployment_agent.prompts import (
    build_deployment_system_prompt,
    build_deployment_user_prompt,
)
from agents.deployment_agent.risk_calculator import calculate_deployment_risk
from core.llm_client import LLMClient
from db.models.incident import Incident
from tools.github.client import GitHubClient
from tools.github.tools import build_github_registry


async def analyze_deployments(
    incident: Incident,
    *,
    db_session: AsyncSession | None = None,
    llm_client: LLMClient | None = None,
    github_client: GitHubClient | None = None,
) -> DeploymentSummary:
    owned_llm_client = llm_client or LLMClient()
    registry, owned_github_client = build_github_registry(github_client)

    @registry.tool(
        name="score_deployment_risk",
        description="Estimate deployment risk from change type, recency, and historical similarity.",
        parameters={
            "type": "object",
            "properties": {
                "change_type": {"type": "string"},
                "minutes_since_deploy": {"type": "integer"},
                "prior_incident_match": {"type": "boolean"},
            },
            "required": ["change_type", "minutes_since_deploy", "prior_incident_match"],
        },
    )
    async def score_deployment_risk(
        change_type: str,
        minutes_since_deploy: int,
        prior_incident_match: bool,
    ) -> dict[str, float]:
        return {
            "risk_score": calculate_deployment_risk(
                change_type,
                minutes_since_deploy,
                prior_incident_match,
            )
        }

    context: dict[str, Any] = {
        "title": incident.title,
        "summary": incident.summary,
        "service": incident.raw_payload.get("labels", {}).get("service", "unknown"),
        "severity": incident.severity,
    }
    result = await agent_loop(
        llm_client=owned_llm_client,
        system_prompt=build_deployment_system_prompt(),
        user_message=build_deployment_user_prompt(context),
        tools=[
            "get_recent_deployments",
            "get_commit_diff",
            "get_rollback_candidates",
            "score_deployment_risk",
        ],
        registry=registry,
        output_schema=DeploymentSummary,
        state=context,
        incident_id=incident.id,
        agent_name="deployment_agent",
        db_session=db_session,
    )
    assert isinstance(result, DeploymentSummary)

    if llm_client is None:
        await owned_llm_client.close()
    if github_client is None:
        await owned_github_client.close()
    return result
