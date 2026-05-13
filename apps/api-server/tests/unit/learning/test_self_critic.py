"""Tests for ReasoningSelfCritic (Phase 46)."""

from __future__ import annotations

from learning.self_critic import ReasoningSelfCritic


class TestReasoningSelfCritic:
    def setup_method(self):
        self.critic = ReasoningSelfCritic()

    def _sound_critique(self, **overrides):
        defaults = dict(
            incident_id="INC-001",
            confidence=0.80,
            evidence_count=5,
            hypothesis_count=3,
            contradiction_count=0,
            has_mechanism=True,
            has_propagation_path=True,
            why_statement_count=4,
            escalation_recommended=False,
        )
        defaults.update(overrides)
        return self.critic.critique(**defaults)

    def test_sound_reasoning_produces_no_findings(self):
        report = self._sound_critique()
        assert report.total_findings == 0
        assert report.reasoning_quality_score == 1.0
        assert report.recommended_confidence_adjustment == 0.0

    def test_zero_evidence_triggers_evidence_gap(self):
        report = self._sound_critique(evidence_count=0)
        codes = [f.finding_code for f in report.findings]
        assert "EVIDENCE_GAP" in codes

    def test_evidence_gap_is_high_severity(self):
        report = self._sound_critique(evidence_count=0)
        high = [f for f in report.findings if f.finding_code == "EVIDENCE_GAP"]
        assert high[0].severity == "high"

    def test_thin_evidence_with_high_confidence_triggers_finding(self):
        report = self._sound_critique(evidence_count=1, confidence=0.80)
        codes = [f.finding_code for f in report.findings]
        assert "THIN_EVIDENCE_HIGH_CONFIDENCE" in codes

    def test_thin_evidence_low_confidence_no_finding(self):
        report = self._sound_critique(evidence_count=1, confidence=0.40)
        codes = [f.finding_code for f in report.findings]
        assert "THIN_EVIDENCE_HIGH_CONFIDENCE" not in codes

    def test_single_hypothesis_triggers_finding(self):
        report = self._sound_critique(hypothesis_count=1)
        codes = [f.finding_code for f in report.findings]
        assert "SINGLE_HYPOTHESIS" in codes

    def test_high_confidence_without_mechanism_triggers_finding(self):
        report = self._sound_critique(confidence=0.80, has_mechanism=False)
        codes = [f.finding_code for f in report.findings]
        assert "CONFIDENT_WITHOUT_MECHANISM" in codes

    def test_low_confidence_without_mechanism_no_finding(self):
        report = self._sound_critique(confidence=0.50, has_mechanism=False)
        codes = [f.finding_code for f in report.findings]
        assert "CONFIDENT_WITHOUT_MECHANISM" not in codes

    def test_missing_propagation_path_with_high_confidence_triggers_finding(self):
        report = self._sound_critique(has_propagation_path=False, confidence=0.70)
        codes = [f.finding_code for f in report.findings]
        assert "MISSING_PROPAGATION_PATH" in codes

    def test_contradictions_unexplained_when_few_why_statements(self):
        report = self._sound_critique(contradiction_count=2, why_statement_count=1)
        codes = [f.finding_code for f in report.findings]
        assert "CONTRADICTIONS_UNEXPLAINED" in codes

    def test_contradictions_with_adequate_why_no_finding(self):
        report = self._sound_critique(contradiction_count=2, why_statement_count=3)
        codes = [f.finding_code for f in report.findings]
        assert "CONTRADICTIONS_UNEXPLAINED" not in codes

    def test_escalation_with_high_confidence_triggers_finding(self):
        report = self._sound_critique(escalation_recommended=True, confidence=0.90)
        codes = [f.finding_code for f in report.findings]
        assert "ESCALATION_WITH_HIGH_CONFIDENCE" in codes

    def test_escalation_low_confidence_no_finding(self):
        report = self._sound_critique(escalation_recommended=True, confidence=0.50)
        codes = [f.finding_code for f in report.findings]
        assert "ESCALATION_WITH_HIGH_CONFIDENCE" not in codes

    def test_high_severity_reduces_quality_score(self):
        report = self._sound_critique(evidence_count=0)  # high severity
        assert report.reasoning_quality_score < 1.0

    def test_high_severity_produces_negative_confidence_adjustment(self):
        report = self._sound_critique(evidence_count=0)
        assert report.recommended_confidence_adjustment < 0.0

    def test_confidence_adjustment_bounded(self):
        # Trigger multiple high-severity findings
        report = self._sound_critique(
            evidence_count=0, hypothesis_count=1, has_mechanism=False
        )
        assert report.recommended_confidence_adjustment >= -0.20

    def test_critique_summary_mentions_finding_codes(self):
        report = self._sound_critique(evidence_count=0)
        assert "EVIDENCE_GAP" in report.critique_summary

    def test_sound_critique_summary(self):
        report = self._sound_critique()
        assert "sound" in report.critique_summary.lower()

    def test_raw_artifact_empty_why_triggers_finding(self):
        report = self.critic.critique(
            incident_id="INC-001",
            confidence=0.70,
            evidence_count=3,
            hypothesis_count=2,
            contradiction_count=0,
            has_mechanism=True,
            has_propagation_path=True,
            why_statement_count=0,
            escalation_recommended=False,
            raw_artifact={"why": [], "uncertainty_note": "low confidence"},
        )
        codes = [f.finding_code for f in report.findings]
        assert "EMPTY_WHY_STATEMENTS" in codes

    def test_raw_artifact_missing_uncertainty_note_triggers_finding(self):
        report = self.critic.critique(
            incident_id="INC-001",
            confidence=0.60,
            evidence_count=3,
            hypothesis_count=2,
            contradiction_count=0,
            has_mechanism=True,
            has_propagation_path=True,
            why_statement_count=2,
            escalation_recommended=False,
            raw_artifact={"why": ["because x"], "uncertainty_note": ""},
        )
        codes = [f.finding_code for f in report.findings]
        assert "MISSING_UNCERTAINTY_NOTE" in codes

    def test_critique_report_to_dict(self):
        report = self._sound_critique()
        d = report.to_dict()
        for key in [
            "incident_id", "findings", "total_findings", "high_severity_count",
            "reasoning_quality_score", "recommended_confidence_adjustment",
            "critique_summary",
        ]:
            assert key in d
