"""Degraded mode verifier — validates system behavior under partial failure conditions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class DegradedModeReport:
    telemetry_survivable: bool
    replay_survivable: bool
    llm_fallback_active: bool
    async_resilience_verified: bool
    failover_verified: bool
    estimated_recovery_seconds: float
    degradation_scenarios: list[dict[str, Any]]
    overall_survivability: float
    recommendation: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "telemetry_survivable": self.telemetry_survivable,
            "replay_survivable": self.replay_survivable,
            "llm_fallback_active": self.llm_fallback_active,
            "async_resilience_verified": self.async_resilience_verified,
            "failover_verified": self.failover_verified,
            "estimated_recovery_seconds": self.estimated_recovery_seconds,
            "degradation_scenarios": self.degradation_scenarios,
            "overall_survivability": self.overall_survivability,
            "recommendation": self.recommendation,
        }


_DEGRADATION_SCENARIOS = [
    {
        "scenario": "telemetry_stream_loss",
        "description": "All telemetry input ceases",
        "expected_behavior": "system_enters_uncertainty_mode",
        "recovery": "auto",
        "max_recovery_seconds": 30.0,
    },
    {
        "scenario": "llm_api_unavailable",
        "description": "LLM provider returns 503",
        "expected_behavior": "fallback_classifier_activates",
        "recovery": "auto",
        "max_recovery_seconds": 10.0,
    },
    {
        "scenario": "replay_dataset_corrupted",
        "description": "Replay dataset fails checksum",
        "expected_behavior": "evaluation_halted_not_degraded",
        "recovery": "manual",
        "max_recovery_seconds": 300.0,
    },
    {
        "scenario": "async_worker_timeout",
        "description": "Async worker exceeds timeout",
        "expected_behavior": "circuit_breaker_trips",
        "recovery": "auto",
        "max_recovery_seconds": 60.0,
    },
    {
        "scenario": "database_connection_lost",
        "description": "PostgreSQL connection pool exhausted",
        "expected_behavior": "memory_fallback_activates",
        "recovery": "auto",
        "max_recovery_seconds": 30.0,
    },
]


class DegradedModeVerifier:
    """Verify system survivability under defined degradation conditions.

    Each scenario is checked against the system profile — the system must
    have documented responses to each failure mode before claiming survivability.
    """

    def verify(self, system_profile: dict[str, Any]) -> DegradedModeReport:
        scenarios = self._evaluate_scenarios(system_profile)

        telemetry_ok = any(
            s["scenario"] == "telemetry_stream_loss" and s["survived"] for s in scenarios
        )
        replay_ok = any(
            s["scenario"] == "replay_dataset_corrupted" and s["survived"] for s in scenarios
        )
        llm_fallback = bool(system_profile.get("llm_fallback"))
        async_resilience = bool(system_profile.get("async_resilience"))
        failover = bool(system_profile.get("failover_documented"))

        survived_count = sum(1 for s in scenarios if s["survived"])
        survivability = round(survived_count / len(scenarios), 4) if scenarios else 0.0

        recovery_times = [s["estimated_recovery_seconds"] for s in scenarios]
        avg_recovery = (
            round(sum(recovery_times) / len(recovery_times), 1) if recovery_times else 0.0
        )

        return DegradedModeReport(
            telemetry_survivable=telemetry_ok,
            replay_survivable=replay_ok,
            llm_fallback_active=llm_fallback,
            async_resilience_verified=async_resilience,
            failover_verified=failover,
            estimated_recovery_seconds=avg_recovery,
            degradation_scenarios=scenarios,
            overall_survivability=survivability,
            recommendation=self._recommendation(survivability, scenarios),
        )

    def _evaluate_scenarios(self, profile: dict[str, Any]) -> list[dict[str, Any]]:
        capability_map = {
            "telemetry_stream_loss": profile.get("uncertainty_mode"),
            "llm_api_unavailable": profile.get("llm_fallback"),
            "replay_dataset_corrupted": profile.get("replay_integrity_checks"),
            "async_worker_timeout": profile.get("circuit_breakers"),
            "database_connection_lost": profile.get("memory_fallback"),
        }

        results = []
        for scenario in _DEGRADATION_SCENARIOS:
            key = scenario["scenario"]
            survived = bool(capability_map.get(key, False))
            recovery = (
                scenario["max_recovery_seconds"]
                if survived
                else scenario["max_recovery_seconds"] * 5.0
            )
            results.append(
                {
                    "scenario": key,
                    "description": scenario["description"],
                    "expected_behavior": scenario["expected_behavior"],
                    "survived": survived,
                    "recovery_mode": scenario["recovery"],
                    "estimated_recovery_seconds": recovery,
                }
            )
        return results

    def _recommendation(self, survivability: float, scenarios: list[dict[str, Any]]) -> str:
        failed = [s["scenario"] for s in scenarios if not s["survived"]]
        if survivability >= 1.0:
            return "System handles all documented degradation scenarios."
        if survivability >= 0.60:
            return f"System survives most failures. Unhandled: {', '.join(failed)}."
        return (
            "System is fragile under failure conditions. "
            f"Critical gaps: {', '.join(failed)}. "
            "Do not deploy without remediation."
        )
