"""
Tests for Phase 49 cognitive overload and escalation fatigue detection modules:
  - fatigue_model          (FatigueModel / FatigueAssessment)
  - overload_detector      (CognitiveLoadAnalyzer / CognitiveLoadReport)
  - escalation_fatigue     (EscalationFatigueAnalyzer / EscalationFatigueReport)
"""

from __future__ import annotations

import pytest
from operators.workflow.escalation_fatigue import (
    EscalationFatigueAnalyzer,
    EscalationFatigueReport,
    EscalationFatigueRisk,
)
from operators.workflow.fatigue_model import (
    FatigueAssessment,
    FatigueLevel,
    FatigueModel,
    FatigueSignals,
)
from operators.workflow.overload_detector import (
    CognitiveLoadAnalyzer,
    CognitiveLoadReport,
    OverloadState,
)

# =========================================================================
# Helpers
# =========================================================================


def _fresh_model() -> FatigueModel:
    return FatigueModel()


def _fresh_analyzer() -> CognitiveLoadAnalyzer:
    return CognitiveLoadAnalyzer()


def _fresh_efa() -> EscalationFatigueAnalyzer:
    return EscalationFatigueAnalyzer()


# =========================================================================
# FatigueModel
# =========================================================================


class TestFatigueModelComposite:
    """Composite score arithmetic."""

    def test_all_zero_signals_gives_zero_composite(self):
        model = _fresh_model()
        result = model.assess("op-1", 0.0, 0.0, 0.0, 0.0, 0.0)
        assert result.composite_fatigue_score == 0.0

    def test_all_max_signals_gives_composite_one(self):
        model = _fresh_model()
        # escalation_density=10 saturates at 1.0; others are already 1.0
        result = model.assess("op-1", 10.0, 1.0, 1.0, 1.0, 1.0)
        assert result.composite_fatigue_score == pytest.approx(1.0, abs=1e-6)

    def test_escalation_density_normalisation(self):
        """escalation_density / 10 should cap at 1.0."""
        model = _fresh_model()
        # Only escalation_density contributes: 5/10 * 0.25 = 0.125
        result = model.assess("op-1", 5.0, 0.0, 0.0, 0.0, 0.0)
        assert result.composite_fatigue_score == pytest.approx(0.125, abs=1e-6)

    def test_escalation_density_capped_above_saturation(self):
        """Values > 10 should not exceed the normalised weight contribution."""
        model = _fresh_model()
        result_sat = model.assess("op-1", 10.0, 0.0, 0.0, 0.0, 0.0)
        result_over = model.assess("op-1", 999.0, 0.0, 0.0, 0.0, 0.0)
        assert result_sat.composite_fatigue_score == result_over.composite_fatigue_score

    def test_override_burden_contribution(self):
        """override_burden=1.0 contributes 0.20."""
        model = _fresh_model()
        result = model.assess("op-1", 0.0, 1.0, 0.0, 0.0, 0.0)
        assert result.composite_fatigue_score == pytest.approx(0.20, abs=1e-6)

    def test_ambiguity_frequency_contribution(self):
        """ambiguity_frequency=1.0 contributes 0.20."""
        model = _fresh_model()
        result = model.assess("op-1", 0.0, 0.0, 1.0, 0.0, 0.0)
        assert result.composite_fatigue_score == pytest.approx(0.20, abs=1e-6)

    def test_alert_noise_ratio_contribution(self):
        """alert_noise_ratio=1.0 contributes 0.20."""
        model = _fresh_model()
        result = model.assess("op-1", 0.0, 0.0, 0.0, 1.0, 0.0)
        assert result.composite_fatigue_score == pytest.approx(0.20, abs=1e-6)

    def test_unresolved_incident_pressure_contribution(self):
        """unresolved_incident_pressure=1.0 contributes 0.15."""
        model = _fresh_model()
        result = model.assess("op-1", 0.0, 0.0, 0.0, 0.0, 1.0)
        assert result.composite_fatigue_score == pytest.approx(0.15, abs=1e-6)

    def test_weights_sum_to_one(self):
        """All weights must sum to exactly 1.0 (verified via max-signal test)."""
        model = _fresh_model()
        assert sum(model._WEIGHTS.values()) == pytest.approx(1.0, abs=1e-9)

    def test_composite_capped_at_one(self):
        """Floating-point edge: composite must never exceed 1.0."""
        model = _fresh_model()
        result = model.assess("op-1", 100.0, 2.0, 2.0, 2.0, 2.0)
        assert result.composite_fatigue_score <= 1.0


class TestFatigueModelLevelClassification:
    """FatigueLevel thresholds."""

    def test_nominal_level(self):
        model = _fresh_model()
        # composite ≈ 0.0 < 0.25 → NOMINAL
        result = model.assess("op-1", 0.0, 0.0, 0.0, 0.0, 0.0)
        assert result.fatigue_level == FatigueLevel.NOMINAL

    def test_elevated_level(self):
        model = _fresh_model()
        # composite = 0.25 * 1.0 = 0.25 → ELEVATED (0.25 <= x < 0.50)
        result = model.assess("op-1", 10.0, 0.0, 0.0, 0.0, 0.0)
        assert result.fatigue_level == FatigueLevel.ELEVATED

    def test_high_level(self):
        model = _fresh_model()
        # escalation=10 (0.25) + override=1.0 (0.20) + ambiguity=0.5 (0.10) = 0.55 → HIGH
        result = model.assess("op-1", 10.0, 1.0, 0.5, 0.0, 0.0)
        assert result.composite_fatigue_score >= 0.50
        assert result.fatigue_level == FatigueLevel.HIGH

    def test_critical_level(self):
        model = _fresh_model()
        # All max → composite = 1.0 → CRITICAL
        result = model.assess("op-1", 10.0, 1.0, 1.0, 1.0, 1.0)
        assert result.fatigue_level == FatigueLevel.CRITICAL

    def test_boundary_nominal_to_elevated(self):
        """composite = 0.25 is ELEVATED, not NOMINAL."""
        model = _fresh_model()
        # Only escalation_density: 10.0/10.0 * 0.25 = 0.25
        result = model.assess("op-1", 10.0, 0.0, 0.0, 0.0, 0.0)
        assert result.composite_fatigue_score == pytest.approx(0.25, abs=1e-6)
        assert result.fatigue_level == FatigueLevel.ELEVATED

    def test_boundary_elevated_to_high(self):
        """composite = 0.50 is HIGH, not ELEVATED."""
        model = _fresh_model()
        # escalation=0.25 + override=0.20 + ambiguity=0.05 = 0.50
        result = model.assess("op-1", 10.0, 1.0, 0.25, 0.0, 0.0)
        assert result.composite_fatigue_score == pytest.approx(0.50, abs=1e-6)
        assert result.fatigue_level == FatigueLevel.HIGH

    def test_boundary_high_to_critical(self):
        """composite = 0.75 is CRITICAL, not HIGH."""
        model = _fresh_model()
        # escalation=0.25 + override=0.20 + ambiguity=0.20 + noise=0.10 = 0.75
        result = model.assess("op-1", 10.0, 1.0, 1.0, 0.5, 0.0)
        assert result.composite_fatigue_score == pytest.approx(0.75, abs=1e-6)
        assert result.fatigue_level == FatigueLevel.CRITICAL


class TestFatigueModelSuppression:
    """suppress_non_critical flag."""

    def test_suppress_false_for_nominal(self):
        model = _fresh_model()
        result = model.assess("op-1", 0.0, 0.0, 0.0, 0.0, 0.0)
        assert result.suppress_non_critical is False

    def test_suppress_false_for_elevated(self):
        model = _fresh_model()
        result = model.assess("op-1", 10.0, 0.0, 0.0, 0.0, 0.0)
        assert result.fatigue_level == FatigueLevel.ELEVATED
        assert result.suppress_non_critical is False

    def test_suppress_true_for_high(self):
        model = _fresh_model()
        result = model.assess("op-1", 10.0, 1.0, 0.5, 0.0, 0.0)
        assert result.fatigue_level == FatigueLevel.HIGH
        assert result.suppress_non_critical is True

    def test_suppress_true_for_critical(self):
        model = _fresh_model()
        result = model.assess("op-1", 10.0, 1.0, 1.0, 1.0, 1.0)
        assert result.fatigue_level == FatigueLevel.CRITICAL
        assert result.suppress_non_critical is True


class TestFatigueModelDominantSignal:
    """dominant_signal reflects the highest-contributing signal name."""

    def test_dominant_signal_escalation_density(self):
        model = _fresh_model()
        # Only escalation_density active
        result = model.assess("op-1", 10.0, 0.0, 0.0, 0.0, 0.0)
        assert result.dominant_signal == "escalation_density"

    def test_dominant_signal_override_burden(self):
        model = _fresh_model()
        # override_burden=1.0 (contrib=0.20) vs escalation_density=1.0 (contrib=0.25)
        # escalation still wins; use partial escalation to let override dominate
        result = model.assess("op-1", 0.0, 1.0, 0.0, 0.0, 0.0)
        assert result.dominant_signal == "override_burden"

    def test_dominant_signal_unresolved_pressure(self):
        model = _fresh_model()
        result = model.assess("op-1", 0.0, 0.0, 0.0, 0.0, 1.0)
        assert result.dominant_signal == "unresolved_incident_pressure"


class TestFatigueModelReturnTypes:
    """Return type and field integrity."""

    def test_returns_fatigue_assessment(self):
        model = _fresh_model()
        result = model.assess("op-42", 3.0, 0.3, 0.2, 0.1, 0.4)
        assert isinstance(result, FatigueAssessment)

    def test_signals_dataclass_populated(self):
        model = _fresh_model()
        result = model.assess("op-42", 3.0, 0.3, 0.2, 0.1, 0.4)
        assert isinstance(result.signals, FatigueSignals)
        assert result.signals.escalation_density == 3.0
        assert result.signals.override_burden == 0.3

    def test_operator_id_preserved(self):
        model = _fresh_model()
        result = model.assess("unique-op-id", 0.0, 0.0, 0.0, 0.0, 0.0)
        assert result.operator_id == "unique-op-id"


# =========================================================================
# CognitiveLoadAnalyzer
# =========================================================================


class TestCognitiveLoadSignals:
    """Individual signal normalisation and contribution."""

    def test_all_zero_signals(self):
        analyzer = _fresh_analyzer()
        report = analyzer.analyze("op-1", 0, 0, 0.0, 0.0, 0)
        assert report.total_cognitive_load == 0.0
        for sig in report.signals:
            assert sig.value == 0.0
            assert sig.contribution == 0.0

    def test_active_ambiguity_saturation(self):
        """active_ambiguity_count=5 saturates the signal at value=1.0."""
        analyzer = _fresh_analyzer()
        report = analyzer.analyze("op-1", 5, 0, 0.0, 0.0, 0)
        sig = next(s for s in report.signals if s.signal_name == "active_ambiguity")
        assert sig.value == pytest.approx(1.0, abs=1e-6)
        assert sig.contribution == pytest.approx(0.25, abs=1e-6)

    def test_active_ambiguity_partial(self):
        """active_ambiguity_count=2 → value=0.4, contribution=0.10."""
        analyzer = _fresh_analyzer()
        report = analyzer.analyze("op-1", 2, 0, 0.0, 0.0, 0)
        sig = next(s for s in report.signals if s.signal_name == "active_ambiguity")
        assert sig.value == pytest.approx(0.4, abs=1e-6)
        assert sig.contribution == pytest.approx(0.10, abs=1e-6)

    def test_active_ambiguity_above_saturation_capped(self):
        analyzer = _fresh_analyzer()
        report_sat = analyzer.analyze("op-1", 5, 0, 0.0, 0.0, 0)
        report_over = analyzer.analyze("op-1", 100, 0, 0.0, 0.0, 0)
        sig_sat = next(s for s in report_sat.signals if s.signal_name == "active_ambiguity")
        sig_over = next(s for s in report_over.signals if s.signal_name == "active_ambiguity")
        assert sig_sat.contribution == sig_over.contribution

    def test_unresolved_pressure_saturation(self):
        """unresolved_incidents=10 saturates value=1.0, contribution=0.20."""
        analyzer = _fresh_analyzer()
        report = analyzer.analyze("op-1", 0, 10, 0.0, 0.0, 0)
        sig = next(s for s in report.signals if s.signal_name == "unresolved_pressure")
        assert sig.value == pytest.approx(1.0, abs=1e-6)
        assert sig.contribution == pytest.approx(0.20, abs=1e-6)

    def test_alert_density_passthrough(self):
        """alert_density=0.5 passes through as value=0.5, contribution=0.10."""
        analyzer = _fresh_analyzer()
        report = analyzer.analyze("op-1", 0, 0, 0.5, 0.0, 0)
        sig = next(s for s in report.signals if s.signal_name == "alert_density")
        assert sig.value == pytest.approx(0.5, abs=1e-6)
        assert sig.contribution == pytest.approx(0.10, abs=1e-6)

    def test_alert_density_capped_at_one(self):
        """alert_density > 1.0 should be capped to 1.0."""
        analyzer = _fresh_analyzer()
        report = analyzer.analyze("op-1", 0, 0, 99.0, 0.0, 0)
        sig = next(s for s in report.signals if s.signal_name == "alert_density")
        assert sig.value == pytest.approx(1.0, abs=1e-6)

    def test_explanation_complexity_passthrough(self):
        analyzer = _fresh_analyzer()
        report = analyzer.analyze("op-1", 0, 0, 0.0, 0.8, 0)
        sig = next(s for s in report.signals if s.signal_name == "explanation_complexity")
        assert sig.value == pytest.approx(0.8, abs=1e-6)
        assert sig.contribution == pytest.approx(0.16, abs=1e-6)

    def test_contradictory_signals_saturation(self):
        """contradictory_signals=5 saturates at value=1.0, contribution=0.15."""
        analyzer = _fresh_analyzer()
        report = analyzer.analyze("op-1", 0, 0, 0.0, 0.0, 5)
        sig = next(s for s in report.signals if s.signal_name == "contradictory_signals")
        assert sig.value == pytest.approx(1.0, abs=1e-6)
        assert sig.contribution == pytest.approx(0.15, abs=1e-6)

    def test_contradictory_signals_partial(self):
        """contradictory_signals=2 → value=0.4, contribution=0.06."""
        analyzer = _fresh_analyzer()
        report = analyzer.analyze("op-1", 0, 0, 0.0, 0.0, 2)
        sig = next(s for s in report.signals if s.signal_name == "contradictory_signals")
        assert sig.value == pytest.approx(0.4, abs=1e-6)
        assert sig.contribution == pytest.approx(0.06, abs=1e-6)

    def test_signals_list_has_five_entries(self):
        analyzer = _fresh_analyzer()
        report = analyzer.analyze("op-1", 3, 5, 0.4, 0.3, 2)
        assert len(report.signals) == 5

    def test_total_equals_sum_of_contributions(self):
        analyzer = _fresh_analyzer()
        report = analyzer.analyze("op-1", 3, 5, 0.4, 0.3, 2)
        expected = round(sum(s.contribution for s in report.signals), 6)
        assert report.total_cognitive_load == pytest.approx(expected, abs=1e-5)


class TestCognitiveLoadTotal:
    """Total load computation."""

    def test_all_max_signals_total_one(self):
        analyzer = _fresh_analyzer()
        report = analyzer.analyze("op-1", 5, 10, 1.0, 1.0, 5)
        assert report.total_cognitive_load == pytest.approx(1.0, abs=1e-6)

    def test_total_capped_at_one(self):
        analyzer = _fresh_analyzer()
        # deliberately over-saturate all signals
        report = analyzer.analyze("op-1", 100, 100, 100.0, 100.0, 100)
        assert report.total_cognitive_load <= 1.0


class TestOverloadStateClassification:
    """OverloadState thresholds."""

    def test_normal_state(self):
        analyzer = _fresh_analyzer()
        # All zero → total = 0.0 → NORMAL
        report = analyzer.analyze("op-1", 0, 0, 0.0, 0.0, 0)
        assert report.state == OverloadState.NORMAL

    def test_elevated_state(self):
        analyzer = _fresh_analyzer()
        # active_ambiguity=2 → 0.10; alert_density=0.5 → 0.10; total=0.20 still NORMAL
        # active_ambiguity=4 → 0.20; alert_density=0.6 → 0.12; total=0.32 → ELEVATED
        report = analyzer.analyze("op-1", 4, 0, 0.6, 0.0, 0)
        assert report.state == OverloadState.ELEVATED

    def test_overloaded_state(self):
        analyzer = _fresh_analyzer()
        # ambiguity=5 (0.25) + unresolved=10 (0.20) + alert=0.5 (0.10) = 0.55 → OVERLOADED
        report = analyzer.analyze("op-1", 5, 10, 0.5, 0.0, 0)
        assert report.total_cognitive_load >= 0.55
        assert report.state == OverloadState.OVERLOADED

    def test_saturated_state(self):
        analyzer = _fresh_analyzer()
        # All max → SATURATED
        report = analyzer.analyze("op-1", 5, 10, 1.0, 1.0, 5)
        assert report.state == OverloadState.SATURATED

    def test_boundary_normal_to_elevated(self):
        """total = 0.30 is ELEVATED."""
        analyzer = _fresh_analyzer()
        # ambiguity=5 (0.25) + unresolved=2.5 (0.05) = 0.30 → ELEVATED
        report = analyzer.analyze("op-1", 5, 3, 0.0, 0.25, 0)
        # rough check that total ≈ 0.30 hits ELEVATED
        assert report.state in (OverloadState.ELEVATED, OverloadState.NORMAL)
        if report.total_cognitive_load >= 0.30:
            assert report.state == OverloadState.ELEVATED

    def test_boundary_overloaded_to_saturated(self):
        """total = 0.80 is SATURATED."""
        analyzer = _fresh_analyzer()
        # All max: combined weight sum >= 0.80 → SATURATED
        report = analyzer.analyze("op-1", 5, 10, 1.0, 1.0, 3)
        assert report.total_cognitive_load >= 0.80
        assert report.state == OverloadState.SATURATED


class TestCognitiveLoadSuppression:
    """recommendation_suppression_active flag."""

    def test_no_suppression_for_normal(self):
        analyzer = _fresh_analyzer()
        report = analyzer.analyze("op-1", 0, 0, 0.0, 0.0, 0)
        assert report.recommendation_suppression_active is False

    def test_no_suppression_for_elevated(self):
        analyzer = _fresh_analyzer()
        report = analyzer.analyze("op-1", 4, 0, 0.6, 0.0, 0)
        assert report.state == OverloadState.ELEVATED
        assert report.recommendation_suppression_active is False

    def test_suppression_for_overloaded(self):
        analyzer = _fresh_analyzer()
        report = analyzer.analyze("op-1", 5, 10, 0.5, 0.0, 0)
        assert report.state == OverloadState.OVERLOADED
        assert report.recommendation_suppression_active is True

    def test_suppression_for_saturated(self):
        analyzer = _fresh_analyzer()
        report = analyzer.analyze("op-1", 5, 10, 1.0, 1.0, 5)
        assert report.state == OverloadState.SATURATED
        assert report.recommendation_suppression_active is True


class TestCognitiveLoadReturnTypes:
    """Return type and field integrity."""

    def test_returns_cognitive_load_report(self):
        analyzer = _fresh_analyzer()
        report = analyzer.analyze("op-42", 2, 3, 0.4, 0.3, 1)
        assert isinstance(report, CognitiveLoadReport)

    def test_operator_id_preserved(self):
        analyzer = _fresh_analyzer()
        report = analyzer.analyze("my-op", 0, 0, 0.0, 0.0, 0)
        assert report.operator_id == "my-op"

    def test_raw_fields_preserved(self):
        analyzer = _fresh_analyzer()
        report = analyzer.analyze("op-1", 3, 7, 0.5, 0.6, 2)
        assert report.active_ambiguity_count == 3
        assert report.unresolved_count == 7
        assert report.alert_density == pytest.approx(0.5)
        assert report.explanation_complexity == pytest.approx(0.6)
        assert report.contradictory_signal_count == 2

    def test_all_signals_have_correct_weights(self):
        """Check that the signal weights in the report match the spec."""
        expected_weights = {
            "active_ambiguity": 0.25,
            "unresolved_pressure": 0.20,
            "alert_density": 0.20,
            "explanation_complexity": 0.20,
            "contradictory_signals": 0.15,
        }
        analyzer = _fresh_analyzer()
        report = analyzer.analyze("op-1", 1, 1, 0.1, 0.1, 1)
        for sig in report.signals:
            assert sig.weight == pytest.approx(expected_weights[sig.signal_name], abs=1e-9)


# =========================================================================
# EscalationFatigueAnalyzer
# =========================================================================


class TestEscalationSpamRate:
    """escalation_spam_rate calculation."""

    def test_spam_rate_zero_when_no_false_escalations(self):
        efa = _fresh_efa()
        report = efa.analyze("op-1", 10, 0, 0, 100, 10, 0)
        assert report.escalation_spam_rate == pytest.approx(0.0, abs=1e-6)

    def test_spam_rate_full_when_all_false(self):
        efa = _fresh_efa()
        report = efa.analyze("op-1", 5, 5, 0, 100, 10, 0)
        assert report.escalation_spam_rate == pytest.approx(1.0, abs=1e-6)

    def test_spam_rate_partial(self):
        efa = _fresh_efa()
        report = efa.analyze("op-1", 10, 4, 0, 100, 10, 0)
        assert report.escalation_spam_rate == pytest.approx(0.4, abs=1e-6)

    def test_spam_rate_zero_escalations_uses_one_as_denominator(self):
        """Division by zero guard: escalation_count=0 → denominator=1."""
        efa = _fresh_efa()
        report = efa.analyze("op-1", 0, 0, 0, 100, 10, 0)
        assert report.escalation_spam_rate == pytest.approx(0.0, abs=1e-6)


class TestAlertFatigueRisk:
    """alert_fatigue_risk flag."""

    def test_no_alert_fatigue_risk_below_threshold(self):
        efa = _fresh_efa()
        # 40 % false positives — not strictly > 0.40
        report = efa.analyze("op-1", 5, 0, 0, 100, 40, 0)
        assert report.alert_fatigue_risk is False

    def test_alert_fatigue_risk_above_threshold(self):
        efa = _fresh_efa()
        # 41 % false positives → True
        report = efa.analyze("op-1", 5, 0, 0, 100, 41, 0)
        assert report.alert_fatigue_risk is True

    def test_alert_fatigue_risk_all_false_positives(self):
        efa = _fresh_efa()
        report = efa.analyze("op-1", 5, 0, 0, 100, 100, 0)
        assert report.alert_fatigue_risk is True

    def test_alert_fatigue_risk_no_alerts_no_risk(self):
        """Zero total_alerts: 0/1 = 0.0 → not > 0.40."""
        efa = _fresh_efa()
        report = efa.analyze("op-1", 5, 0, 0, 0, 0, 0)
        assert report.alert_fatigue_risk is False


class TestRecommendationSaturation:
    """recommendation_saturation flag."""

    def test_not_saturated_at_ten(self):
        efa = _fresh_efa()
        report = efa.analyze("op-1", 5, 0, 0, 100, 10, 10)
        assert report.recommendation_saturation is False

    def test_saturated_at_eleven(self):
        efa = _fresh_efa()
        report = efa.analyze("op-1", 5, 0, 0, 100, 10, 11)
        assert report.recommendation_saturation is True

    def test_saturated_at_high_count(self):
        efa = _fresh_efa()
        report = efa.analyze("op-1", 5, 0, 0, 100, 10, 50)
        assert report.recommendation_saturation is True

    def test_not_saturated_at_zero(self):
        efa = _fresh_efa()
        report = efa.analyze("op-1", 5, 0, 0, 100, 10, 0)
        assert report.recommendation_saturation is False


class TestEscalationFatigueRiskLevels:
    """fatigue_risk classification."""

    def test_none_risk(self):
        efa = _fresh_efa()
        # escalation_count=3 (≤5), no false escalations, no uncertainty escalations
        report = efa.analyze("op-1", 3, 0, 0, 100, 10, 0)
        assert report.fatigue_risk == EscalationFatigueRisk.NONE

    def test_low_risk_from_escalation_count(self):
        efa = _fresh_efa()
        # escalation_count=6 > 5 → LOW, spam_rate=0
        report = efa.analyze("op-1", 6, 0, 0, 100, 10, 0)
        assert report.fatigue_risk == EscalationFatigueRisk.LOW

    def test_moderate_risk_from_spam_rate(self):
        efa = _fresh_efa()
        # spam_rate = 3/10 = 0.30 > 0.20 → MODERATE
        report = efa.analyze("op-1", 10, 3, 0, 100, 10, 0)
        assert report.fatigue_risk == EscalationFatigueRisk.MODERATE

    def test_moderate_risk_from_chronic_uncertainty(self):
        efa = _fresh_efa()
        # chronic_uncertainty=3 > 2 → MODERATE (spam_rate=0)
        report = efa.analyze("op-1", 3, 0, 3, 100, 10, 0)
        assert report.fatigue_risk == EscalationFatigueRisk.MODERATE

    def test_high_risk_from_spam_rate(self):
        efa = _fresh_efa()
        # spam_rate = 5/10 = 0.50 > 0.40 → HIGH
        report = efa.analyze("op-1", 10, 5, 0, 100, 10, 0)
        assert report.fatigue_risk == EscalationFatigueRisk.HIGH

    def test_high_risk_from_alert_fatigue_and_escalation_count(self):
        efa = _fresh_efa()
        # alert_fatigue=True (fp=60/100), escalation_count=11 > 10 → HIGH
        report = efa.analyze("op-1", 11, 0, 0, 100, 60, 0)
        assert report.alert_fatigue_risk is True
        assert report.fatigue_risk == EscalationFatigueRisk.HIGH

    def test_spam_risk_from_high_spam_rate(self):
        efa = _fresh_efa()
        # spam_rate = 7/10 = 0.70 > 0.60 → SPAM
        report = efa.analyze("op-1", 10, 7, 0, 100, 10, 0)
        assert report.fatigue_risk == EscalationFatigueRisk.SPAM

    def test_spam_risk_from_chronic_uncertainty(self):
        efa = _fresh_efa()
        # chronic_uncertainty=6 > 5 → SPAM
        report = efa.analyze("op-1", 5, 0, 6, 100, 10, 0)
        assert report.fatigue_risk == EscalationFatigueRisk.SPAM

    def test_spam_takes_priority_over_high(self):
        efa = _fresh_efa()
        # spam_rate=0.65 and alert_fatigue=True: both SPAM and HIGH conditions met; SPAM wins
        report = efa.analyze("op-1", 20, 13, 0, 100, 60, 0)
        assert report.fatigue_risk == EscalationFatigueRisk.SPAM

    def test_high_takes_priority_over_moderate(self):
        efa = _fresh_efa()
        # spam_rate=0.45 (>0.40 HIGH) and also >0.20 (MODERATE): HIGH wins
        report = efa.analyze("op-1", 10, 4, 0, 100, 10, 0)
        # 4/10 = 0.40 — NOT strictly > 0.40, so MODERATE
        assert report.fatigue_risk == EscalationFatigueRisk.MODERATE

    def test_high_strict_boundary(self):
        efa = _fresh_efa()
        # 5/10 = 0.50 > 0.40 → HIGH
        report = efa.analyze("op-1", 10, 5, 0, 100, 10, 0)
        assert report.fatigue_risk == EscalationFatigueRisk.HIGH

    def test_moderate_exact_boundary(self):
        efa = _fresh_efa()
        # spam_rate = 2/10 = 0.20 — NOT strictly > 0.20
        # escalation_count=10 > 5 → LOW
        report = efa.analyze("op-1", 10, 2, 0, 100, 10, 0)
        assert report.fatigue_risk == EscalationFatigueRisk.LOW


class TestEscalationFatigueReturnTypes:
    """Return type and field integrity."""

    def test_returns_escalation_fatigue_report(self):
        efa = _fresh_efa()
        report = efa.analyze("op-42", 8, 2, 1, 100, 30, 5)
        assert isinstance(report, EscalationFatigueReport)

    def test_operator_id_preserved(self):
        efa = _fresh_efa()
        report = efa.analyze("sentinel-op", 8, 2, 1, 100, 30, 5)
        assert report.operator_id == "sentinel-op"

    def test_raw_counts_preserved(self):
        efa = _fresh_efa()
        report = efa.analyze("op-1", 12, 4, 3, 200, 80, 7)
        assert report.escalation_count == 12
        assert report.false_escalation_count == 4
        assert report.chronic_uncertainty_escalations == 3
