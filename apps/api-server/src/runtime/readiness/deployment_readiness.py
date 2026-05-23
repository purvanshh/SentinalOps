"""Deployment readiness validator — honest, non-inflated readiness classification."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ReadinessLevel(str, Enum):
    EXPERIMENTAL = "experimental"
    STAGING_CAPABLE = "staging_capable"
    PRODUCTION_CAPABLE = "production_capable"
    HIGH_RISK_PRODUCTION = "high_risk_production"
    AUTONOMY_PROHIBITED = "autonomy_prohibited"


# Readiness criteria per level — all must be satisfied to reach that level.
_LEVEL_REQUIREMENTS: dict[ReadinessLevel, list[str]] = {
    ReadinessLevel.EXPERIMENTAL: [
        "has_unit_tests",
        "has_basic_logging",
    ],
    ReadinessLevel.STAGING_CAPABLE: [
        "has_unit_tests",
        "has_integration_tests",
        "has_basic_logging",
        "has_error_handling",
        "test_pass_rate_above_90",
    ],
    ReadinessLevel.PRODUCTION_CAPABLE: [
        "has_unit_tests",
        "has_integration_tests",
        "has_load_tests",
        "has_basic_logging",
        "has_structured_logging",
        "has_error_handling",
        "has_circuit_breakers",
        "has_health_checks",
        "test_pass_rate_above_95",
        "has_reproducibility_validation",
        "has_adversarial_evaluation",
    ],
    ReadinessLevel.HIGH_RISK_PRODUCTION: [
        "has_unit_tests",
        "has_integration_tests",
        "has_load_tests",
        "has_basic_logging",
        "has_structured_logging",
        "has_error_handling",
        "has_circuit_breakers",
        "has_health_checks",
        "test_pass_rate_above_95",
        "has_reproducibility_validation",
        "has_adversarial_evaluation",
        "human_approval_required",
        "audit_logging_enabled",
    ],
    ReadinessLevel.AUTONOMY_PROHIBITED: [],  # Never autonomous
}


@dataclass
class ReadinessReport:
    level: ReadinessLevel
    satisfied_criteria: list[str]
    missing_criteria: list[str]
    blocking_gaps: list[str]
    autonomy_permitted: bool
    summary: str
    caveats: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "level": self.level.value,
            "satisfied_criteria": self.satisfied_criteria,
            "missing_criteria": self.missing_criteria,
            "blocking_gaps": self.blocking_gaps,
            "autonomy_permitted": self.autonomy_permitted,
            "summary": self.summary,
            "caveats": self.caveats,
        }


class DeploymentReadinessValidator:
    """Conservative readiness classifier.

    Deliberately conservative: it requires explicit evidence of each criterion.
    Absence of evidence = criterion not satisfied.

    This system will never self-promote to a higher readiness level without
    explicit evidence. It operates under the assumption that unstated
    capabilities do not exist.
    """

    def assess(self, system_profile: dict[str, Any]) -> ReadinessReport:
        criteria = self._extract_criteria(system_profile)
        satisfied = [c for c in criteria if criteria[c]]
        missing = [c for c in criteria if not criteria[c]]

        level = self._classify_level(satisfied)
        blocking = self._blocking_gaps(level, missing)
        autonomy = self._autonomy_permitted(level, system_profile)
        caveats = self._build_caveats(system_profile, level)
        summary = self._summarize(level, missing, blocking, autonomy)

        return ReadinessReport(
            level=level,
            satisfied_criteria=satisfied,
            missing_criteria=missing,
            blocking_gaps=blocking,
            autonomy_permitted=autonomy,
            summary=summary,
            caveats=caveats,
        )

    def _extract_criteria(self, profile: dict[str, Any]) -> dict[str, bool]:
        test_pass_rate = float(profile.get("test_pass_rate", 0.0))
        return {
            "has_unit_tests": bool(profile.get("unit_tests")),
            "has_integration_tests": bool(profile.get("integration_tests")),
            "has_load_tests": bool(profile.get("load_tests")),
            "has_basic_logging": bool(profile.get("basic_logging")),
            "has_structured_logging": bool(profile.get("structured_logging")),
            "has_error_handling": bool(profile.get("error_handling")),
            "has_circuit_breakers": bool(profile.get("circuit_breakers")),
            "has_health_checks": bool(profile.get("health_checks")),
            "test_pass_rate_above_90": test_pass_rate >= 0.90,
            "test_pass_rate_above_95": test_pass_rate >= 0.95,
            "has_reproducibility_validation": bool(profile.get("reproducibility_validation")),
            "has_adversarial_evaluation": bool(profile.get("adversarial_evaluation")),
            "human_approval_required": bool(profile.get("human_approval_required")),
            "audit_logging_enabled": bool(profile.get("audit_logging")),
        }

    def _classify_level(self, satisfied: list[str]) -> ReadinessLevel:
        # Work top-down from production levels; return highest level where ALL requirements are met.
        for level in [
            ReadinessLevel.HIGH_RISK_PRODUCTION,
            ReadinessLevel.PRODUCTION_CAPABLE,
            ReadinessLevel.STAGING_CAPABLE,
            ReadinessLevel.EXPERIMENTAL,
        ]:
            required = _LEVEL_REQUIREMENTS[level]
            if all(r in satisfied for r in required):
                return level
        return ReadinessLevel.EXPERIMENTAL

    def _blocking_gaps(self, level: ReadinessLevel, missing: list[str]) -> list[str]:
        if level == ReadinessLevel.PRODUCTION_CAPABLE:
            return [
                m for m in missing if m in _LEVEL_REQUIREMENTS[ReadinessLevel.HIGH_RISK_PRODUCTION]
            ]
        return []

    def _autonomy_permitted(self, level: ReadinessLevel, profile: dict[str, Any]) -> bool:
        if level in (ReadinessLevel.EXPERIMENTAL, ReadinessLevel.AUTONOMY_PROHIBITED):
            return False
        if level == ReadinessLevel.STAGING_CAPABLE:
            return False
        if level in (ReadinessLevel.PRODUCTION_CAPABLE, ReadinessLevel.HIGH_RISK_PRODUCTION):
            # Autonomy only permitted if human override explicitly documented
            return bool(profile.get("human_override_documented"))
        return False

    def _build_caveats(self, profile: dict[str, Any], level: ReadinessLevel) -> list[str]:
        caveats = []
        if level in (ReadinessLevel.EXPERIMENTAL, ReadinessLevel.STAGING_CAPABLE):
            caveats.append(
                "This system is simulation-only. No production telemetry has been processed."
            )
        if not profile.get("real_incident_validation"):
            caveats.append(
                "Evaluation is based on synthetic/simulated incidents, not production data."
            )
        if not profile.get("security_audit"):
            caveats.append("No external security audit has been completed.")
        if profile.get("llm_dependency"):
            caveats.append(
                "System depends on external LLM API — availability and behavior not guaranteed."
            )
        return caveats

    def _summarize(
        self,
        level: ReadinessLevel,
        missing: list[str],
        blocking: list[str],
        autonomy: bool,
    ) -> str:
        level_label = level.value.replace("_", " ").title()
        autonomy_str = (
            "Autonomous operation: NOT PERMITTED"
            if not autonomy
            else "Autonomous operation: permitted with oversight"
        )
        if missing:
            gap_str = f" Missing {len(missing)} criteria."
        else:
            gap_str = " All evaluated criteria satisfied."
        return f"Readiness: {level_label}.{gap_str} {autonomy_str}."
