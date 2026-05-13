"""
Operational chaos integration layer for Phase 48.

Wires together the chaos, observability, execution truth, and causal ambiguity
components into the replay pipeline. Produces a ChaosReplayResult that extends
the standard ReplayResult with five operational realism scores:

  telemetry_corruption_rate   — fraction of events affected by chaos
  observability_confidence    — mean confidence after completeness/gap/integrity penalties
  execution_truth_score       — fraction of remediations classified as VERIFIED_SUCCESS
  causal_ambiguity_score      — fraction of incidents with STABLE_CAUSE attribution
  replay_instability_score    — fraction of incidents whose causal attribution is unstable

Design constraints:
  - All chaos injection is seeded — deterministic for the same seed.
  - No external I/O. All data comes from the in-process benchmark suite.
  - Scores degrade naturally under chaos; clean scores are never forced.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any

from causality.reality.ambiguity_resolver import AmbiguityResolver, CausalRealityState
from causality.reality.causal_stability import CausalStabilityAnalyzer
from causality.reality.contradiction_graph import ContradictionGraph
from causality.reality.uncertainty_collapse import UncertaintyCollapseGuard
from evaluation.regression.benchmark_replay import ReplayResult, replay_benchmark
from observability.reality.completeness_analyzer import CompletenessAnalyzer
from observability.reality.confidence_penalties import ConfidencePenaltyCalculator
from observability.reality.observability_gaps import ObservabilityGapDetector
from observability.reality.telemetry_integrity import TelemetryIntegrityChecker
from replay.chaos.corruption_models import CorruptionConfig, CorruptionProfile
from replay.chaos.telemetry_chaos import TelemetryChaosEngine

# ---------------------------------------------------------------------------
# Per-incident chaos result
# ---------------------------------------------------------------------------


@dataclass
class IncidentChaosResult:
    incident_id: str
    raw_event_count: int
    chaos_report: dict[str, Any]
    completeness_score: float
    observability_confidence: float
    causal_state: str
    is_causally_stable: bool
    stability_score: float
    collapse_risk_score: float
    should_hold_back: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "incident_id": self.incident_id,
            "raw_event_count": self.raw_event_count,
            "chaos_report": self.chaos_report,
            "completeness_score": round(self.completeness_score, 4),
            "observability_confidence": round(self.observability_confidence, 4),
            "causal_state": self.causal_state,
            "is_causally_stable": self.is_causally_stable,
            "stability_score": round(self.stability_score, 4),
            "collapse_risk_score": round(self.collapse_risk_score, 4),
            "should_hold_back": self.should_hold_back,
        }


# ---------------------------------------------------------------------------
# Aggregate chaos replay result
# ---------------------------------------------------------------------------


@dataclass
class ChaosReplayResult:
    base_result: ReplayResult
    chaos_profile: str
    chaos_seed: int
    incident_chaos_results: list[IncidentChaosResult] = field(default_factory=list)

    # Five operational realism scores
    telemetry_corruption_rate: float = 0.0
    observability_confidence: float = 0.0
    execution_truth_score: float = 0.0
    causal_ambiguity_score: float = 0.0
    replay_instability_score: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "base": self.base_result.to_dict(),
            "chaos_profile": self.chaos_profile,
            "chaos_seed": self.chaos_seed,
            "telemetry_corruption_rate": round(self.telemetry_corruption_rate, 4),
            "observability_confidence": round(self.observability_confidence, 4),
            "execution_truth_score": round(self.execution_truth_score, 4),
            "causal_ambiguity_score": round(self.causal_ambiguity_score, 4),
            "replay_instability_score": round(self.replay_instability_score, 4),
            "incident_count": len(self.incident_chaos_results),
            "per_incident": [r.to_dict() for r in self.incident_chaos_results],
        }


# ---------------------------------------------------------------------------
# Synthetic event generator for benchmark incidents
# ---------------------------------------------------------------------------


def _synthetic_events_for_incident(
    incident_id: str,
    rng: random.Random,
    event_count: int = 12,
) -> list[dict[str, Any]]:
    """
    Generate synthetic telemetry events for an incident.

    Used when the benchmark suite carries abstract incident records rather than
    raw event streams. Produces enough structural variety for completeness and
    integrity checks to behave realistically.
    """
    kinds = ["metric", "log", "alert", "deployment", "metric", "log", "metric"]
    severities = ["info", "warning", "error", "critical", "info", "warning", "error"]
    services = ["api-gateway", "db-primary", "cache", "auth-service", "queue"]

    base_ts = 1_700_000_000 + rng.randint(0, 86_400)
    events = []
    for i in range(event_count):
        ts = base_ts + i * rng.randint(10, 120)
        kind = rng.choice(kinds)
        sev = rng.choice(severities)
        svc = rng.choice(services)
        events.append(
            {
                "event_id": f"{incident_id[:8]}_ev{i:03d}",
                "kind": kind,
                "timestamp_iso": f"2023-11-14T{(ts % 86400) // 3600:02d}"
                f":{(ts % 3600) // 60:02d}:{ts % 60:02d}Z",
                "service": svc,
                "severity": sev,
                "incident_id": incident_id,
                "payload": {"value": rng.uniform(0.0, 1.0), "description": f"ev_{i}"},
                "source": "synthetic",
            }
        )
    return events


# ---------------------------------------------------------------------------
# Synthetic hypotheses for causal analysis
# ---------------------------------------------------------------------------


def _synthetic_hypotheses(
    incident_id: str,
    rng: random.Random,
) -> list[dict[str, Any]]:
    mechanisms = [
        "db_connection_pool_exhaustion",
        "network_partition",
        "memory_leak",
        "cpu_throttling",
        "deploy_config_change",
    ]
    chosen = rng.sample(mechanisms, k=rng.randint(2, 4))
    hyps = []
    remaining = 1.0
    for i, mech in enumerate(chosen):
        if i == len(chosen) - 1:
            conf = max(0.10, remaining)
        else:
            conf = round(rng.uniform(0.15, min(0.60, remaining - 0.10 * (len(chosen) - i - 1))), 3)
            remaining -= conf
        evidence_count = rng.randint(1, 4)
        hyps.append(
            {
                "mechanism": mech,
                "confidence": conf,
                "supporting_evidence": [f"ev_{mech[:6]}_{j}" for j in range(evidence_count)],
            }
        )
    return hyps


# ---------------------------------------------------------------------------
# Per-incident chaos analysis
# ---------------------------------------------------------------------------


def _analyze_incident_chaos(
    incident_id: str,
    rng: random.Random,
    chaos_engine: TelemetryChaosEngine,
    config: CorruptionConfig,
) -> IncidentChaosResult:
    raw_events = _synthetic_events_for_incident(incident_id, rng)
    corrupted_events, chaos_report = chaos_engine.inject(raw_events, config)

    # Observability scoring
    completeness = CompletenessAnalyzer().analyze(corrupted_events)
    gap_report = ObservabilityGapDetector().detect(corrupted_events)
    integrity_report = TelemetryIntegrityChecker().check(corrupted_events)
    penalty_calc = ConfidencePenaltyCalculator()
    penalty = penalty_calc.compute(
        original_confidence=0.80,
        completeness=completeness,
        gap_report=gap_report,
        integrity_report=integrity_report,
    )

    # Causal analysis
    hyps = _synthetic_hypotheses(incident_id, rng)
    graph = ContradictionGraph()
    graph.add_from_hypotheses(hyps)
    contradiction_report = graph.analyze()

    resolver = AmbiguityResolver()
    ambiguity = resolver.resolve(
        hyps,
        has_observation_conflict=contradiction_report.has_irreconcilable,
    )

    stability = CausalStabilityAnalyzer().analyze(hyps)

    top_gap = 0.0
    if len(hyps) >= 2:
        sorted_h = sorted(hyps, key=lambda h: float(h.get("confidence", 0.0)), reverse=True)
        top_gap = float(sorted_h[0]["confidence"]) - float(sorted_h[1]["confidence"])

    collapse_guard = UncertaintyCollapseGuard()
    collapse = collapse_guard.check(
        proposed_confidence=float(hyps[0]["confidence"]) if hyps else 0.5,
        evidence_count=len(hyps[0].get("supporting_evidence", [])) if hyps else 0,
        hypothesis_count=len(hyps),
        top_gap=top_gap,
        telemetry_completeness=completeness.overall,
    )

    return IncidentChaosResult(
        incident_id=incident_id,
        raw_event_count=len(raw_events),
        chaos_report=chaos_report.to_dict(),
        completeness_score=completeness.overall,
        observability_confidence=penalty.penalised_confidence,
        causal_state=ambiguity.state.value,
        is_causally_stable=stability.is_stable,
        stability_score=stability.stability_score,
        collapse_risk_score=collapse.collapse_risk_score,
        should_hold_back=collapse.should_hold_back_attribution,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def replay_benchmark_with_chaos(
    profile: CorruptionProfile = CorruptionProfile.NETWORK_PARTITION,
    seed: int = 42,
    incident_ids: list[str] | None = None,
) -> ChaosReplayResult:
    """
    Run the standard replay benchmark, then overlay operational chaos scoring.

    Parameters
    ----------
    profile:
        Which CorruptionProfile to apply. Defaults to NETWORK_PARTITION.
    seed:
        RNG seed for deterministic replay.
    incident_ids:
        Optional list of incident IDs to analyse. When None, synthetic IDs
        are generated from the base benchmark result.
    """
    base = replay_benchmark()

    if incident_ids is None:
        incident_ids = [f"inc_{i:04d}" for i in range(base.total_incidents or 10)]

    config = CorruptionConfig.from_profile(profile)
    chaos_engine = TelemetryChaosEngine(seed=seed)

    rng = random.Random(seed)
    incident_results: list[IncidentChaosResult] = []
    for inc_id in incident_ids:
        result = _analyze_incident_chaos(inc_id, rng, chaos_engine, config)
        incident_results.append(result)

    if not incident_results:
        return ChaosReplayResult(
            base_result=base,
            chaos_profile=profile.value,
            chaos_seed=seed,
        )

    # Aggregate the five realism scores
    all_corruption_rates = [
        r.chaos_report.get("effective_loss_rate", 0.0) for r in incident_results
    ]
    telemetry_corruption_rate = sum(all_corruption_rates) / len(all_corruption_rates)

    observability_confidence = sum(r.observability_confidence for r in incident_results) / len(
        incident_results
    )

    # execution_truth_score: fraction without hold-back (proxy for verified success)
    execution_truth_score = sum(
        1 for r in incident_results if not r.should_hold_back
    ) / len(incident_results)

    causal_ambiguity_score = sum(
        1 for r in incident_results if r.causal_state == CausalRealityState.STABLE_CAUSE.value
    ) / len(incident_results)

    replay_instability_score = sum(
        1 for r in incident_results if not r.is_causally_stable
    ) / len(incident_results)

    return ChaosReplayResult(
        base_result=base,
        chaos_profile=profile.value,
        chaos_seed=seed,
        incident_chaos_results=incident_results,
        telemetry_corruption_rate=round(telemetry_corruption_rate, 4),
        observability_confidence=round(observability_confidence, 4),
        execution_truth_score=round(execution_truth_score, 4),
        causal_ambiguity_score=round(causal_ambiguity_score, 4),
        replay_instability_score=round(replay_instability_score, 4),
    )
