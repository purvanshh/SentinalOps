"""
runtime_operator_integration.py — Phase 49 Commit 7

Top-level integration module that wires all operator-centric workflow systems
together into a single runtime orchestrator. Provides:

  - OperatorFacingAssessment: per-incident, operator-relevant assessment
  - RuntimeOperatorMetrics:   per-session runtime operator health metrics
  - OperatorRuntimeOrchestrator: unified entry point to all sub-analyzers
"""

from __future__ import annotations

from dataclasses import dataclass

from .actionability import ActionabilityAnalyzer, ActionabilityClass
from .decision_lifecycle import DecisionLifecycleTracker
from .disagreement_analysis import DisagreementAnalyzer
from .escalation_fatigue import EscalationFatigueAnalyzer
from .escalation_pathway import EscalationChain
from .explainability_quality import ExplainabilityQualityAnalyzer
from .fatigue_model import FatigueModel
from .longitudinal_operator_eval import LongitudinalOperatorEvaluator, SessionSummary
from .narrative_consistency import NarrativeConsistencyChecker
from .operational_friction import OperationalFrictionAnalyzer
from .operator_alignment import OperatorAlignmentBenchmark
from .operator_session import SessionManager
from .overload_detector import CognitiveLoadAnalyzer
from .rationale_validator import RationaleValidator
from .remediation_usefulness import RemediationUsefulnessEvaluator
from .trust_realism import TrustRealismModel
from .usefulness_evaluator import OperationalUsefulnessEvaluator
from .workflow_benchmark import WorkflowBenchmark

# ---------------------------------------------------------------------------
# Output dataclasses
# ---------------------------------------------------------------------------


@dataclass
class OperatorFacingAssessment:
    """
    Per-incident, operator-relevant assessment distilled from all sub-analyzers.

    Boolean fields encode actionable yes/no verdicts that gate how a
    recommendation is surfaced to an operator under incident pressure.
    """

    incident_id: str
    operator_id: str

    # --- Operator-facing verdicts (derived booleans) ---
    would_operator_trust: bool
    """True if trust_score >= 0.55 AND overall explainability >= 0.55."""

    would_reduce_burden: bool
    """True if operator_fatigue <= 0.60 AND remediation usefulness >= 0.55."""

    is_actionable_under_pressure: bool
    """
    True if the actionability class is not OPERATIONALLY_VAGUE or
    DANGEROUSLY_AMBIGUOUS AND total operational friction <= 0.70.
    """

    # --- Scalar measurements ---
    recommendation_usefulness: float  # 0.0–1.0
    escalation_fatigue_risk: str  # EscalationFatigueRisk.value
    cognitive_load: float  # 0.0–1.0  (operator_fatigue proxy)
    override_burden: float  # 0.0–1.0
    explanation_clarity: float  # 0.0–1.0
    trust_realism: float  # 0.0–1.0


@dataclass
class RuntimeOperatorMetrics:
    """
    Aggregated per-session runtime metrics capturing operator health and
    AI system usefulness from the operator's perspective.
    """

    operator_id: str
    session_id: str
    recommendation_usefulness: float  # 0.0–1.0
    escalation_fatigue_risk_level: str  # EscalationFatigueRisk.value
    cognitive_load: float  # 0.0–1.0
    override_burden: float  # 0.0–1.0
    explanation_clarity: float  # 0.0–1.0
    trust_realism_score: float  # 0.0–1.0
    is_suppressing_non_critical: bool  # from FatigueModel suppress_non_critical
    overall_operator_usefulness: float  # 0.0–1.0


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


class OperatorRuntimeOrchestrator:
    """
    Top-level integration class that instantiates and coordinates all
    operator-centric workflow sub-analyzers.

    Design notes
    ------------
    - Sub-analyzers are stateless scorers; state that needs to persist across
      calls (longitudinal data) is managed by the stateful evaluators
      (LongitudinalOperatorEvaluator, SessionManager, etc.).
    - All public methods are pure in the sense that they do not mutate
      caller-visible state; only record_session_outcome() and the
      longitudinal evaluator accumulate state internally.
    """

    def __init__(self) -> None:
        self.session_manager = SessionManager()
        self.lifecycle_tracker = DecisionLifecycleTracker()
        self.escalation_chain = EscalationChain()
        self.explainability_analyzer = ExplainabilityQualityAnalyzer()
        self.rationale_validator = RationaleValidator()
        self.consistency_checker = NarrativeConsistencyChecker()
        self.actionability_analyzer = ActionabilityAnalyzer()
        self.usefulness_evaluator_rem = RemediationUsefulnessEvaluator()
        self.friction_analyzer = OperationalFrictionAnalyzer()
        self.fatigue_model = FatigueModel()
        self.overload_detector = CognitiveLoadAnalyzer()
        self.escalation_fatigue_analyzer = EscalationFatigueAnalyzer()
        self.alignment_benchmark = OperatorAlignmentBenchmark()
        self.trust_model = TrustRealismModel()
        self.disagreement_analyzer = DisagreementAnalyzer()
        self.workflow_benchmark = WorkflowBenchmark()
        self.usefulness_evaluator = OperationalUsefulnessEvaluator()
        self.longitudinal_evaluator = LongitudinalOperatorEvaluator()

    # ------------------------------------------------------------------
    # Primary assessment entry point
    # ------------------------------------------------------------------

    def assess_incident(
        self,
        operator_id: str,
        incident_id: str,
        narrative: str,
        recommendation: str,
        confidence: float,
        evidence_refs: list[str],
        uncertainty_flags: list[str],
        contradictions: list[str],
        rollback_plan: str | None,
        dependencies: list[str],
        blast_radius_mentioned: bool,
        escalation_reason: str | None,
        operator_fatigue: float,
        concurrent_incidents: int,
        trust_score: float,
    ) -> OperatorFacingAssessment:
        """
        Run a full operator-facing assessment for a single incident.

        Parameters
        ----------
        operator_id:
            Unique identifier of the responding operator.
        incident_id:
            Unique identifier of the active incident.
        narrative:
            Full text of the AI-generated incident narrative.
        recommendation:
            Full text of the AI-generated remediation recommendation.
        confidence:
            AI model's stated confidence in the root-cause assessment (0.0–1.0).
        evidence_refs:
            List of evidence reference identifiers cited in the narrative.
        uncertainty_flags:
            List of uncertainty signals the model identified and reported.
        contradictions:
            List of contradiction descriptions the model acknowledged.
        rollback_plan:
            Text describing the rollback procedure, or None if absent.
        dependencies:
            List of external dependency names acknowledged in context.
        blast_radius_mentioned:
            True if the recommendation explicitly states the blast radius.
        escalation_reason:
            Human-readable reason an escalation was triggered, or None.
        operator_fatigue:
            Current operator fatigue level (0.0 = fresh, 1.0 = exhausted).
        concurrent_incidents:
            Number of incidents the operator is currently managing.
        trust_score:
            Operator's current trust score for the AI system (0.0–1.0).

        Returns
        -------
        OperatorFacingAssessment with verdicts and scalar measurements.
        """
        # 1. Explainability -------------------------------------------------
        exp_score = self.explainability_analyzer.score(
            incident_id=incident_id,
            narrative=narrative,
            evidence_refs=evidence_refs,
            confidence=confidence,
            uncertainty_flags=uncertainty_flags,
            contradictions=contradictions,
        )

        # 2. Actionability --------------------------------------------------
        act_score = self.actionability_analyzer.analyze(
            incident_id=incident_id,
            recommendation=recommendation,
            rollback_plan=rollback_plan,
            dependencies=dependencies,
            blast_radius_mentioned=blast_radius_mentioned,
        )

        # 3. Operational friction -------------------------------------------
        friction_report = self.friction_analyzer.analyze(
            incident_id=incident_id,
            recommendation=recommendation,
            operator_fatigue=operator_fatigue,
            concurrent_incidents=concurrent_incidents,
            confidence=confidence,
        )

        # 4. Escalation fatigue --------------------------------------------
        # Derive plausible escalation metrics from available signals.
        escalation_count = max(1, concurrent_incidents)
        false_escalation_count = 0
        chronic_uncertainty_esc = len(uncertainty_flags) // 2
        total_alerts = max(concurrent_incidents, 1)
        false_positive_alerts = len(contradictions)
        unaccepted_recommendations = 0

        fatigue_report = self.escalation_fatigue_analyzer.analyze(
            operator_id=operator_id,
            escalation_count=escalation_count,
            false_escalation_count=false_escalation_count,
            chronic_uncertainty_escalations=chronic_uncertainty_esc,
            total_alerts=total_alerts,
            false_positive_alerts=false_positive_alerts,
            unaccepted_recommendations=unaccepted_recommendations,
        )

        # 5. Remediation usefulness -----------------------------------------
        rem_usefulness = self.usefulness_evaluator_rem.evaluate(
            incident_id=incident_id,
            recommendation=recommendation,
            mechanism=narrative[:120],  # use the narrative opening as mechanism context
        )

        # ------------------------------------------------------------------
        # Derive boolean verdicts
        # ------------------------------------------------------------------
        would_operator_trust = (
            trust_score >= 0.55 and exp_score.overall_explainability_score >= 0.55
        )

        would_reduce_burden = operator_fatigue <= 0.60 and rem_usefulness.usefulness_score >= 0.55

        _vague_classes = (
            ActionabilityClass.OPERATIONALLY_VAGUE,
            ActionabilityClass.DANGEROUSLY_AMBIGUOUS,
        )
        is_actionable_under_pressure = (
            act_score.actionability_class not in _vague_classes
            and friction_report.total_friction <= 0.70
        )

        return OperatorFacingAssessment(
            incident_id=incident_id,
            operator_id=operator_id,
            would_operator_trust=would_operator_trust,
            would_reduce_burden=would_reduce_burden,
            is_actionable_under_pressure=is_actionable_under_pressure,
            recommendation_usefulness=rem_usefulness.usefulness_score,
            escalation_fatigue_risk=fatigue_report.fatigue_risk.value,
            cognitive_load=operator_fatigue,
            override_burden=0.0,  # no override history at incident-assessment time
            explanation_clarity=exp_score.overall_explainability_score,
            trust_realism=trust_score,
        )

    # ------------------------------------------------------------------
    # Runtime metrics computation
    # ------------------------------------------------------------------

    def compute_runtime_metrics(
        self,
        operator_id: str,
        session_id: str,
        recommendation_usefulness: float,
        escalation_density: float,
        override_count: int,
        total_recommendations: int,
        ambiguity_frequency: float,
        alert_noise_ratio: float,
        unresolved_pressure: float,
        active_ambiguity_count: int,
        alert_density: float,
        explanation_complexity: float,
        contradictory_signals: int,
        explanation_clarity: float,
        trust_score: float,
        workflow_quality: float,
        operator_alignment_score: float,
        escalation_burden: float,
        cognitive_load_val: float,
    ) -> RuntimeOperatorMetrics:
        """
        Compute aggregated runtime metrics for an operator session.

        Parameters
        ----------
        operator_id:
            Unique identifier of the operator.
        session_id:
            Unique identifier of the current session.
        recommendation_usefulness:
            Pre-computed average recommendation usefulness for this session
            (0.0–1.0).
        escalation_density:
            Escalations per hour observed in the session.
        override_count:
            Number of overrides issued by the operator this session.
        total_recommendations:
            Total AI recommendations delivered this session.
        ambiguity_frequency:
            Fraction of incidents with ambiguous root cause (0.0–1.0).
        alert_noise_ratio:
            Fraction of total alerts that were false positives (0.0–1.0).
        unresolved_pressure:
            Fraction of assigned incidents still open (0.0–1.0).
        active_ambiguity_count:
            Number of currently active ambiguous incidents.
        alert_density:
            Current alert density, pre-normalised to 0.0–1.0.
        explanation_complexity:
            Complexity score of the most recent AI explanation (0.0–1.0).
        contradictory_signals:
            Number of contradictory diagnostic signal pairs in context.
        explanation_clarity:
            Average explanation clarity for the session (0.0–1.0).
        trust_score:
            Operator's current trust score for the AI system (0.0–1.0).
        workflow_quality:
            Overall workflow quality metric for the session (0.0–1.0).
        operator_alignment_score:
            Operator alignment benchmark score for the session (0.0–1.0).
        escalation_burden:
            Escalation burden score for the session (0.0–1.0).
        cognitive_load_val:
            Pre-computed cognitive load value for the session (0.0–1.0).

        Returns
        -------
        RuntimeOperatorMetrics populated from all sub-analyzer results.
        """
        # Normalise override_burden to [0.0, 1.0]
        override_burden = override_count / max(total_recommendations, 1)
        override_burden = min(1.0, override_burden)

        # --- FatigueModel --------------------------------------------------
        fatigue = self.fatigue_model.assess(
            operator_id=operator_id,
            escalation_density=escalation_density,
            override_burden=override_burden,
            ambiguity_frequency=ambiguity_frequency,
            alert_noise_ratio=alert_noise_ratio,
            unresolved_incident_pressure=unresolved_pressure,
        )

        # --- CognitiveLoadAnalyzer -----------------------------------------
        overload = self.overload_detector.analyze(
            operator_id=operator_id,
            active_ambiguity_count=active_ambiguity_count,
            unresolved_incidents=max(0, int(round(unresolved_pressure * 10))),
            alert_density=alert_density,
            explanation_complexity=explanation_complexity,
            contradictory_signals=contradictory_signals,
        )

        # --- EscalationFatigueAnalyzer (session summary) ------------------
        escalation_count_session = max(1, int(round(escalation_density)))
        _fatigue_summary = self.escalation_fatigue_analyzer.analyze(
            operator_id=operator_id,
            escalation_count=escalation_count_session,
            false_escalation_count=0,
            chronic_uncertainty_escalations=0,
            total_alerts=max(1, int(round(alert_density * 10))),
            false_positive_alerts=int(
                round(alert_noise_ratio * max(1, int(round(alert_density * 10))))
            ),
            unaccepted_recommendations=max(0, override_count),
        )

        # --- OperationalUsefulnessEvaluator --------------------------------
        usefulness_report = self.usefulness_evaluator.evaluate(
            session_id=session_id,
            workflow_quality=workflow_quality,
            operator_alignment=operator_alignment_score,
            escalation_burden=escalation_burden,
            recommendation_quality=recommendation_usefulness,
            cognitive_load_score=cognitive_load_val,
            trust_stability=trust_score,
            remediation_usefulness=recommendation_usefulness,
            explainability_quality=explanation_clarity,
        )

        return RuntimeOperatorMetrics(
            operator_id=operator_id,
            session_id=session_id,
            recommendation_usefulness=recommendation_usefulness,
            escalation_fatigue_risk_level=_fatigue_summary.fatigue_risk.value,
            cognitive_load=overload.total_cognitive_load,
            override_burden=override_burden,
            explanation_clarity=explanation_clarity,
            trust_realism_score=trust_score,
            is_suppressing_non_critical=fatigue.suppress_non_critical,
            overall_operator_usefulness=usefulness_report.overall_usefulness,
        )

    # ------------------------------------------------------------------
    # Session outcome recording
    # ------------------------------------------------------------------

    def record_session_outcome(
        self,
        operator_id: str,
        session_id: str,
        usefulness_score: float,
        trust_at_end: float,
        incidents_handled: int,
        overrides: int,
        escalations: int,
    ) -> None:
        """
        Record the outcome of a completed operator session for longitudinal
        trend tracking.

        Parameters
        ----------
        operator_id:
            Unique identifier of the operator.
        session_id:
            Unique identifier of the completed session.
        usefulness_score:
            Overall usefulness score for the session (0.0–1.0).
        trust_at_end:
            Operator trust level at session end (0.0–1.0).
        incidents_handled:
            Number of incidents handled during the session.
        overrides:
            Number of AI recommendations overridden by the operator.
        escalations:
            Number of escalations triggered during the session.
        """
        summary = SessionSummary(
            session_id=session_id,
            operator_id=operator_id,
            usefulness_score=usefulness_score,
            trust_at_end=trust_at_end,
            incidents_handled=incidents_handled,
            overrides=overrides,
            escalations=escalations,
        )
        self.longitudinal_evaluator.add_session(summary)

    # ------------------------------------------------------------------
    # Longitudinal trend retrieval
    # ------------------------------------------------------------------

    def get_longitudinal_trend(self, operator_id: str):
        """
        Return a LongitudinalTrend for the given operator based on all
        previously recorded session outcomes.

        Parameters
        ----------
        operator_id:
            Unique identifier of the operator whose trend is requested.

        Returns
        -------
        LongitudinalTrend with session count, mean usefulness, trend
        direction, and aggregate incident / override / escalation counts.
        """
        return self.longitudinal_evaluator.evaluate_operator(operator_id)
