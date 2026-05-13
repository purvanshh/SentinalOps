"""
Action risk tier classification for SentinelOps AI.

Every remediation action is classified into one of four tiers:
  READ_ONLY     — observational only, no state changes
  SAFE_MUTATION — low-blast-radius changes, auto-reversible
  HIGH_RISK     — significant state changes, approval required
  DESTRUCTIVE   — irreversible or wide blast-radius, always blocked in SAFE_MODE

The tier drives execution policy in enforcement_guard and execution_node.
"""

from __future__ import annotations

import re
from enum import Enum


class RiskTier(str, Enum):
    READ_ONLY = "READ_ONLY"
    SAFE_MUTATION = "SAFE_MUTATION"
    HIGH_RISK = "HIGH_RISK"
    DESTRUCTIVE = "DESTRUCTIVE"

    @property
    def requires_approval(self) -> bool:
        return self in (RiskTier.HIGH_RISK, RiskTier.DESTRUCTIVE)

    @property
    def blocked_in_safe_mode(self) -> bool:
        return self in (RiskTier.HIGH_RISK, RiskTier.DESTRUCTIVE)


_DESTRUCTIVE_KEYWORDS = frozenset(
    {
        "delete",
        "drop",
        "destroy",
        "terminate",
        "purge",
        "wipe",
        "drain",
        "evict",
        "cordon",
    }
)
_HIGH_RISK_KEYWORDS = frozenset(
    {
        "rollback",
        "scale",
        "deploy",
        "migration",
        "migrate",
        "reset",
        "flush",
        "upgrade",
        "downgrade",
        "replace",
    }
)
_SAFE_MUTATION_KEYWORDS = frozenset(
    {
        "restart",
        "reload",
        "bounce",
        "recycle",
        "refresh",
        "clear cache",
        "rotate",
        "update config",
        "patch",
    }
)
_READ_ONLY_KEYWORDS = frozenset(
    {
        "get",
        "list",
        "describe",
        "fetch",
        "read",
        "show",
        "check",
        "verify",
        "inspect",
        "monitor",
        "query",
        "search",
    }
)


def _word_match(text: str, keyword: str) -> bool:
    """Return True if keyword appears as a whole word in text."""
    return bool(re.search(r"\b" + re.escape(keyword) + r"\b", text))


def classify_action_risk_tier(action: str) -> RiskTier:
    """Classify a remediation action string into a RiskTier.

    Uses whole-word keyword matching so that e.g. 'describe deployment'
    matches READ_ONLY via 'describe' rather than HIGH_RISK via 'deploy'.

    Priority (most-restrictive-wins): DESTRUCTIVE > HIGH_RISK > SAFE_MUTATION
    > READ_ONLY. Default for unknown actions: HIGH_RISK (conservative).
    """
    normalized = action.lower().strip()

    for keyword in _DESTRUCTIVE_KEYWORDS:
        if _word_match(normalized, keyword):
            return RiskTier.DESTRUCTIVE

    for keyword in _HIGH_RISK_KEYWORDS:
        if _word_match(normalized, keyword):
            return RiskTier.HIGH_RISK

    for keyword in _SAFE_MUTATION_KEYWORDS:
        if _word_match(normalized, keyword):
            return RiskTier.SAFE_MUTATION

    for keyword in _READ_ONLY_KEYWORDS:
        if _word_match(normalized, keyword):
            return RiskTier.READ_ONLY

    return RiskTier.HIGH_RISK


def tier_requires_approval(tier: RiskTier) -> bool:
    return tier.requires_approval


def tier_blocked_in_safe_mode(tier: RiskTier) -> bool:
    return tier.blocked_in_safe_mode
