"""
GitHub deployment/workflow adapter for SentinelOps Phase 47.

Converts GitHub webhook events (deployment, deployment_status,
workflow_run, push) into normalized raw dicts for TelemetryNormalizer.

Relevant for correlating deployments with incidents.
"""

from __future__ import annotations

from typing import Any


def adapt_deployment(raw: dict[str, Any]) -> dict[str, Any]:
    """Adapt a GitHub deployment webhook payload."""
    deployment = raw.get("deployment", raw)
    repo = raw.get("repository", {})
    service = repo.get("name", "") or deployment.get("environment", "")
    ts = deployment.get("created_at") or deployment.get("updated_at", "")

    return {
        "event_id": f"gh_deploy_{deployment.get('id', abs(hash(ts + service)))}",
        "kind": "deployment",
        "timestamp_iso": ts,
        "service": service,
        "severity": "info",
        "message": (
            f"Deployment to {deployment.get('environment', 'unknown')} "
            f"ref={deployment.get('ref', '')}"
        ),
        "labels": {
            "environment": str(deployment.get("environment", "")),
            "ref": str(deployment.get("ref", "")),
            "sha": str(deployment.get("sha", "")[:12]),
            "creator": str(deployment.get("creator", {}).get("login", "")),
        },
        "source": "github",
        "payload": deployment,
        "deployment_id": str(deployment.get("id", "")),
        "incident_id": None,
    }


def adapt_deployment_status(raw: dict[str, Any]) -> dict[str, Any]:
    """Adapt a GitHub deployment_status webhook payload."""
    status = raw.get("deployment_status", raw)
    deployment = raw.get("deployment", {})
    repo = raw.get("repository", {})
    service = repo.get("name", "") or deployment.get("environment", "")
    ts = status.get("created_at") or status.get("updated_at", "")
    state = status.get("state", "")

    severity_map = {
        "success": "info",
        "failure": "error",
        "error": "error",
        "pending": "info",
        "in_progress": "info",
        "queued": "info",
    }

    return {
        "event_id": f"gh_deploy_status_{status.get('id', abs(hash(ts + state)))}",
        "kind": "deployment",
        "timestamp_iso": ts,
        "service": service,
        "severity": severity_map.get(state, "info"),
        "message": f"Deployment {state}: {status.get('description', '')}",
        "labels": {
            "state": state,
            "environment": str(deployment.get("environment", "")),
            "deployment_id": str(deployment.get("id", "")),
        },
        "source": "github",
        "payload": status,
        "deployment_id": str(deployment.get("id", "")),
        "incident_id": None,
    }


def adapt_workflow_run(raw: dict[str, Any]) -> dict[str, Any]:
    """Adapt a GitHub workflow_run webhook payload."""
    run = raw.get("workflow_run", raw)
    repo = raw.get("repository", {})
    service = repo.get("name", "")
    ts = run.get("created_at", "")
    conclusion = run.get("conclusion") or run.get("status", "")

    severity_map = {
        "failure": "error",
        "cancelled": "warning",
        "timed_out": "error",
        "action_required": "warning",
        "success": "info",
        "skipped": "info",
        "neutral": "info",
    }

    return {
        "event_id": f"gh_workflow_{run.get('id', abs(hash(ts)))}",
        "kind": "deployment",
        "timestamp_iso": ts,
        "service": service,
        "severity": severity_map.get(conclusion, "info"),
        "message": f"Workflow '{run.get('name', '')}' {conclusion}",
        "labels": {
            "workflow": str(run.get("name", "")),
            "branch": str(run.get("head_branch", "")),
            "conclusion": conclusion,
        },
        "source": "github",
        "payload": run,
        "deployment_id": str(run.get("id", "")),
        "incident_id": None,
    }


def adapt_batch(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Adapt a mixed list of GitHub webhook payloads by event type."""
    out: list[dict[str, Any]] = []
    for ev in events:
        kind = ev.get("_event_kind", "")
        if "deployment_status" in kind:
            out.append(adapt_deployment_status(ev))
        elif "deployment" in kind:
            out.append(adapt_deployment(ev))
        elif "workflow_run" in kind:
            out.append(adapt_workflow_run(ev))
        else:
            # Default: treat as deployment
            out.append(adapt_deployment(ev))
    return out
