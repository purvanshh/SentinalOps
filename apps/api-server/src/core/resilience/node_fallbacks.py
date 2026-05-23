"""
Deterministic degraded-mode outputs for non-router graph nodes.

These helpers keep the workflow moving when LLM-backed synthesis fails.
They intentionally trade quality for survivability and transparency.
"""

from __future__ import annotations

from typing import Any


def build_metrics_fallback(*, incident_title: str, error: str) -> dict[str, Any]:
    return {
        "summary": (
            "Metrics summary generated in degraded mode. "
            "Live telemetry collection may still have run, "
            "but LLM synthesis failed."
        ),
        "anomalies": [],
        "correlation_hints": [f"Metrics agent degraded due to provider failure: {error}"],
        "raw_query_links": [],
        "degraded": True,
        "incident_title": incident_title,
    }


def build_logs_fallback(*, error: str) -> dict[str, Any]:
    return {
        "error_signatures": [],
        "temporal_correlations": [],
        "degraded": True,
        "summary": "Logs agent degraded; no synthesized error summary available.",
        "failure_reason": error,
    }


def build_deployment_fallback(*, error: str) -> dict[str, Any]:
    return {
        "recent_changes": [],
        "correlation_with_incident": (
            "Deployment analysis degraded because provider-backed change summarization failed."
        ),
        "degraded": True,
        "failure_reason": error,
    }


def build_root_cause_fallback(*, error: str) -> dict[str, Any]:
    return {
        "status": "insufficient_telemetry",
        "hypotheses": [],
        "strongest_hypothesis_index": None,
        "investigation_log": (
            "Root cause analysis ran in degraded mode. "
            "Deterministic investigation could not form a stable hypothesis "
            f"because upstream summaries were degraded or failed. Error: {error}"
        ),
        "recommended_next_steps": [
            "Review raw metrics and logs",
            "Check recent deployments manually",
            "Escalate to operator triage",
        ],
        "uncertainty": {
            "state": "insufficient_telemetry",
            "confidence": 0.0,
            "uncertainty_score": 1.0,
            "evidence_sufficiency": 0.0,
            "retrieval_grounding": 0.0,
            "hypothesis_stability": 0.0,
            "confidence_interval": {"lower": 0.0, "upper": 0.2},
            "missing_telemetry": ["metrics", "logs", "deployments"],
            "sources": [],
            "contradictions": [],
            "alternative_explanations": [],
            "escalation": {
                "recommended": True,
                "state": "insufficient_telemetry",
                "reasons": ["Provider-backed analysis failed."],
                "triggers": ["insufficient_telemetry"],
                "confidence_threshold": 0.55,
            },
            "rationale": [error],
        },
        "escalation": {
            "recommended": True,
            "state": "insufficient_telemetry",
            "reasons": ["Provider-backed analysis failed."],
            "triggers": ["insufficient_telemetry"],
            "confidence_threshold": 0.55,
        },
        "primary_state": "insufficient_telemetry",
        "narrative": (
            "Unable to determine a confident root cause because evidence collection degraded."
        ),
        "contributing_causes": [],
        "multi_cause": False,
        "degraded": True,
        "failure_reason": error,
    }


def build_risk_fallback(*, error: str) -> dict[str, Any]:
    return {
        "current_impact": {
            "error_rate": 0.0,
            "estimated_users_impacted_so_far": 0,
            "trend": "unknown",
        },
        "blast_radius": {
            "affected_services": [],
            "users_at_risk": {
                "mean": 0,
                "p90": 0,
                "description": (
                    "Risk assessment degraded; blast radius could not be estimated reliably."
                ),
            },
        },
        "remediation_risks": [],
        "degraded": True,
        "failure_reason": error,
    }


def build_remediation_fallback(*, operating_mode: str, error: str) -> dict[str, Any]:
    return {
        "summary": (
            "Remediation planning degraded. "
            "Autonomous execution is disabled until an operator reviews the incident."
        ),
        "steps": [],
        "verify_after_execution": False,
        "degraded": True,
        "operating_mode": operating_mode,
        "failure_reason": error,
    }


def build_postmortem_fallback(
    *, incident_id: str, operating_mode: str, error: str
) -> dict[str, Any]:
    return {
        "title": f"Degraded postmortem for incident {incident_id}",
        "content": (
            "# Degraded Postmortem\n\n"
            f"- Incident ID: `{incident_id}`\n"
            f"- Operating mode: `{operating_mode}`\n"
            "- Result: workflow completed in degraded mode\n"
            f"- Postmortem synthesis failure: {error}\n"
            "- Recommendation: operator should replace this draft"
            " with a manually reviewed postmortem.\n"
        ),
        "degraded": True,
        "failure_reason": error,
    }
