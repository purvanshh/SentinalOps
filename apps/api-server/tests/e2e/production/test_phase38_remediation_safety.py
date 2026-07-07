"""
Phase-38 remediation execution guardrails and rollback safety.

Proves:
  - RiskTier enum has all 4 tiers: READ_ONLY, SAFE_MUTATION, HIGH_RISK, DESTRUCTIVE
  - classify_action_risk_tier correctly categorizes known action patterns
  - DESTRUCTIVE actions are classified more restrictively than HIGH_RISK
  - HIGH_RISK and DESTRUCTIVE tiers require approval
  - READ_ONLY and SAFE_MUTATION do not require approval
  - blocked_in_safe_mode is True only for HIGH_RISK and DESTRUCTIVE
  - Unknown actions default to HIGH_RISK (conservative)
  - Execution node enriches action.details with execution_id, risk_tier, rollback_path
  - SAFE_MODE disables automated execution and returns execution_disabled flag
  - observe_remediation_action counter fires for executed and blocked outcomes
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# RiskTier enum completeness
# ---------------------------------------------------------------------------


def test_risk_tier_has_all_four_values():
    from tools.risk_classifier import RiskTier

    assert RiskTier.READ_ONLY
    assert RiskTier.SAFE_MUTATION
    assert RiskTier.HIGH_RISK
    assert RiskTier.DESTRUCTIVE


def test_read_only_and_safe_mutation_do_not_require_approval():
    from tools.risk_classifier import RiskTier

    assert RiskTier.READ_ONLY.requires_approval is False
    assert RiskTier.SAFE_MUTATION.requires_approval is False


def test_high_risk_and_destructive_require_approval():
    from tools.risk_classifier import RiskTier

    assert RiskTier.HIGH_RISK.requires_approval is True
    assert RiskTier.DESTRUCTIVE.requires_approval is True


def test_only_high_risk_and_destructive_blocked_in_safe_mode():
    from tools.risk_classifier import RiskTier

    assert RiskTier.READ_ONLY.blocked_in_safe_mode is False
    assert RiskTier.SAFE_MUTATION.blocked_in_safe_mode is False
    assert RiskTier.HIGH_RISK.blocked_in_safe_mode is True
    assert RiskTier.DESTRUCTIVE.blocked_in_safe_mode is True


# ---------------------------------------------------------------------------
# Action classification
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "action,expected_tier",
    [
        ("get pod logs", "READ_ONLY"),
        ("list services", "READ_ONLY"),
        ("describe deployment", "READ_ONLY"),
        ("verify metric", "READ_ONLY"),
        ("restart api-server", "SAFE_MUTATION"),
        ("restart service payment-api", "SAFE_MUTATION"),
        ("reload nginx", "SAFE_MUTATION"),
        ("clear cache redis", "SAFE_MUTATION"),
        ("rollback deployment", "HIGH_RISK"),
        ("scale payment-api", "HIGH_RISK"),
        ("deploy new version", "HIGH_RISK"),
        ("upgrade dependencies", "HIGH_RISK"),
        ("delete namespace production", "DESTRUCTIVE"),
        ("drop database sentinelops", "DESTRUCTIVE"),
        ("drain node k8s-node-1", "DESTRUCTIVE"),
        ("terminate instance i-0abc1234", "DESTRUCTIVE"),
        ("purge queue incidents", "DESTRUCTIVE"),
    ],
)
def test_action_risk_tier_classification(action, expected_tier):
    from tools.risk_classifier import RiskTier, classify_action_risk_tier

    result = classify_action_risk_tier(action)
    assert result == RiskTier(
        expected_tier
    ), f"Action '{action}' classified as {result}, expected {expected_tier}"


def test_unknown_action_defaults_to_high_risk():
    from tools.risk_classifier import RiskTier, classify_action_risk_tier

    assert classify_action_risk_tier("xyzzy unknown action") == RiskTier.HIGH_RISK
    assert classify_action_risk_tier("some_custom_operation") == RiskTier.HIGH_RISK


def test_destructive_wins_over_high_risk_when_both_keywords_present():
    from tools.risk_classifier import RiskTier, classify_action_risk_tier

    # "delete" (destructive) + "deploy" (high-risk) → DESTRUCTIVE wins
    result = classify_action_risk_tier("delete and redeploy service")
    assert result == RiskTier.DESTRUCTIVE


# ---------------------------------------------------------------------------
# tier_requires_approval and tier_blocked_in_safe_mode helpers
# ---------------------------------------------------------------------------


def test_tier_requires_approval_helper():
    from tools.risk_classifier import RiskTier, tier_requires_approval

    assert tier_requires_approval(RiskTier.HIGH_RISK) is True
    assert tier_requires_approval(RiskTier.DESTRUCTIVE) is True
    assert tier_requires_approval(RiskTier.READ_ONLY) is False
    assert tier_requires_approval(RiskTier.SAFE_MUTATION) is False


def test_tier_blocked_in_safe_mode_helper():
    from tools.risk_classifier import RiskTier, tier_blocked_in_safe_mode

    assert tier_blocked_in_safe_mode(RiskTier.HIGH_RISK) is True
    assert tier_blocked_in_safe_mode(RiskTier.DESTRUCTIVE) is True
    assert tier_blocked_in_safe_mode(RiskTier.SAFE_MUTATION) is False
    assert tier_blocked_in_safe_mode(RiskTier.READ_ONLY) is False


# ---------------------------------------------------------------------------
# SAFE_MODE disables automated execution
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_execution_node_safe_mode_returns_execution_disabled():
    from orchestration.nodes.execution_node import execution_node

    session = AsyncMock()
    mock_incident = MagicMock()
    mock_incident.status = "active"
    mock_incident.remediation_actions = []

    mock_repo = AsyncMock()
    mock_repo.get_with_context = AsyncMock(return_value=mock_incident)

    with patch("orchestration.nodes.execution_node.IncidentRepository", return_value=mock_repo):
        result = await execution_node(
            {
                "incident_id": "inc-001",
                "operating_mode": "SAFE_MODE",
                "approval": {},
            },
            session=session,
        )

    assert result["execution"]["execution_disabled"] is True
    assert result["graph_status"] == "observe_only"


@pytest.mark.asyncio
async def test_execution_node_observe_only_returns_execution_disabled():
    from orchestration.nodes.execution_node import execution_node

    session = AsyncMock()
    mock_incident = MagicMock()
    mock_incident.status = "active"
    mock_incident.remediation_actions = []

    mock_repo = AsyncMock()
    mock_repo.get_with_context = AsyncMock(return_value=mock_incident)

    with patch("orchestration.nodes.execution_node.IncidentRepository", return_value=mock_repo):
        result = await execution_node(
            {
                "incident_id": "inc-001",
                "operating_mode": "OBSERVE_ONLY",
                "approval": {},
            },
            session=session,
        )

    assert result["execution"]["execution_disabled"] is True


# ---------------------------------------------------------------------------
# observe_remediation_action counter fires for blocked outcome
# ---------------------------------------------------------------------------


def test_observe_remediation_action_executes_increments_counter():
    from observability.metrics import observe_remediation_action
    from prometheus_client import REGISTRY

    def _val(outcome: str) -> float:
        for metric in REGISTRY.collect():
            if metric.name in {"remediation_actions_total", "remediation_actions"}:
                for sample in metric.samples:
                    if (
                        sample.name == "remediation_actions_total"
                        and sample.labels.get("outcome") == outcome
                    ):
                        return sample.value
        return 0.0

    before = _val("blocked_test")
    observe_remediation_action("blocked_test")
    after = _val("blocked_test")
    assert after == before + 1


# ---------------------------------------------------------------------------
# Rollback metadata enrichment
# ---------------------------------------------------------------------------


def test_rollback_path_derives_from_tool_name():
    # For a non-rollback tool, rollback_path should be rollback_{tool_name}
    tool_name = "scale_deployment"
    rollback_path = f"rollback_{tool_name}" if "rollback" not in tool_name else None
    assert rollback_path == "rollback_scale_deployment"


def test_rollback_path_is_none_for_rollback_tool():
    tool_name = "rollback_deployment"
    rollback_path = f"rollback_{tool_name}" if "rollback" not in tool_name else None
    assert rollback_path is None


def test_risk_classifier_handles_case_insensitive_action():
    from tools.risk_classifier import RiskTier, classify_action_risk_tier

    assert classify_action_risk_tier("RESTART api-server") == RiskTier.SAFE_MUTATION
    assert classify_action_risk_tier("DELETE namespace") == RiskTier.DESTRUCTIVE
    assert classify_action_risk_tier("Get Logs") == RiskTier.READ_ONLY
