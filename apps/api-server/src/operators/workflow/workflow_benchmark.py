"""
workflow_benchmark.py — Phase 49 Commit 6

Benchmark that measures multiple dimensions of operator workflow quality
across a single incident, producing a composite score of operational
effectiveness.
"""

from __future__ import annotations

from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclass
class WorkflowBenchmarkResult:
    incident_id: str
    # 1.0 = fully automated, no operator burden
    workload_reduction_score: float
    # 1.0 = no unnecessary escalations
    escalation_reduction_score: float
    ambiguity_handling_quality: float
    remediation_usefulness_score: float
    # 1.0 = no rollbacks needed
    rollback_avoidance_score: float
    trust_preservation_score: float
    # 1.0 = fastest possible decision
    decision_latency_score: float
    # 1.0 = no overrides needed
    override_necessity_score: float
    explanation_usefulness_score: float
    # Equal-weighted average of all 9 component scores
    overall_benchmark_score: float


# ---------------------------------------------------------------------------
# Benchmark class
# ---------------------------------------------------------------------------


class WorkflowBenchmark:
    """Computes per-incident workflow quality across nine dimensions."""

    def run(
        self,
        incident_id: str,
        auto_resolved: bool,
        unnecessary_escalations: int,
        total_escalations: int,
        ambiguity_resolved: bool,
        confidence_at_resolution: float,
        remediation_usefulness: float,
        rollbacks: int,
        trust_score: float,
        decision_latency_seconds: float,
        max_latency_seconds: float,
        overrides: int,
        total_recommendations: int,
        explanation_quality: float,
    ) -> WorkflowBenchmarkResult:
        # --- workload_reduction_score ---
        if auto_resolved:
            workload_reduction = 1.0
        else:
            workload_reduction = max(0.0, 0.5 - 0.05 * overrides)

        # --- escalation_reduction_score ---
        escalation_reduction = max(
            0.0,
            min(
                1.0,
                1.0 - unnecessary_escalations / max(total_escalations, 1),
            ),
        )

        # --- ambiguity_handling_quality ---
        if ambiguity_resolved:
            ambiguity_handling = confidence_at_resolution
        else:
            ambiguity_handling = confidence_at_resolution * 0.5

        # --- remediation_usefulness_score — passed in directly ---
        remediation_usefulness_score = remediation_usefulness

        # --- rollback_avoidance_score ---
        rollback_avoidance = max(0.0, 1.0 - rollbacks * 0.25)

        # --- trust_preservation_score — already 0.0–1.0 ---
        trust_preservation = trust_score

        # --- decision_latency_score ---
        decision_latency = max(
            0.0,
            min(
                1.0,
                1.0 - decision_latency_seconds / max(max_latency_seconds, 1e-9),
            ),
        )

        # --- override_necessity_score ---
        override_necessity = max(
            0.0,
            1.0 - overrides / max(total_recommendations, 1),
        )

        # --- explanation_usefulness_score — passed in directly ---
        explanation_usefulness = explanation_quality

        # --- overall_benchmark_score: equal-weighted mean of 9 scores ---
        scores = [
            workload_reduction,
            escalation_reduction,
            ambiguity_handling,
            remediation_usefulness_score,
            rollback_avoidance,
            trust_preservation,
            decision_latency,
            override_necessity,
            explanation_usefulness,
        ]
        overall = sum(scores) / len(scores)

        return WorkflowBenchmarkResult(
            incident_id=incident_id,
            workload_reduction_score=workload_reduction,
            escalation_reduction_score=escalation_reduction,
            ambiguity_handling_quality=ambiguity_handling,
            remediation_usefulness_score=remediation_usefulness_score,
            rollback_avoidance_score=rollback_avoidance,
            trust_preservation_score=trust_preservation,
            decision_latency_score=decision_latency,
            override_necessity_score=override_necessity,
            explanation_usefulness_score=explanation_usefulness,
            overall_benchmark_score=overall,
        )
