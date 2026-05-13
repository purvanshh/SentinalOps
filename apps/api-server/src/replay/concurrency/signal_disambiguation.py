"""
Signal disambiguation for concurrent incident streams — Phase 48.

Separates telemetry signals into three buckets:
  CAUSAL     — directly caused or accelerated the incident
  CORRELATED — observed alongside the incident but not causally linked
  NOISE      — operationally unrelated (coincidental deployments, background churn)

Core principle:
  Correlation != Causation.

An event that fires during an incident does not cause it.
A deployment that preceded the incident does not necessarily cause it.
The disambiguator uses heuristics to surface uncertainty, not certainty.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class SignalClass(str, Enum):
    CAUSAL = "causal"
    CORRELATED = "correlated"
    NOISE = "noise"
    AMBIGUOUS = "ambiguous"


@dataclass
class ClassifiedSignal:
    event_id: str
    signal_class: SignalClass
    reason: str
    confidence: float  # 0.0–1.0: how confident is the classification


@dataclass
class DisambiguationResult:
    causal: list[ClassifiedSignal]
    correlated: list[ClassifiedSignal]
    noise: list[ClassifiedSignal]
    ambiguous: list[ClassifiedSignal]
    causal_clarity_score: float  # 0.0 = totally ambiguous, 1.0 = unambiguous

    @property
    def total_signals(self) -> int:
        return len(self.causal) + len(self.correlated) + len(self.noise) + len(self.ambiguous)

    def to_dict(self) -> dict[str, Any]:
        return {
            "causal_count": len(self.causal),
            "correlated_count": len(self.correlated),
            "noise_count": len(self.noise),
            "ambiguous_count": len(self.ambiguous),
            "total_signals": self.total_signals,
            "causal_clarity_score": round(self.causal_clarity_score, 4),
        }


_CAUSAL_KINDS = {"alert", "topology_change"}
_CORRELATED_KINDS = {"log", "metric"}
_NOISE_KINDS = {"deployment"}

# Noise signals: synthetic markers inserted by NoiseDeploymentInjector
_NOISE_MARKER = "_noise_deployment"

# Known neutral severities
_NEUTRAL_SEVERITIES = {"info"}


class SignalDisambiguator:
    """
    Classifies events from a concurrent incident stream into causal/correlated/noise.

    Heuristics (conservative — prefer ambiguous over false certainty):
      1. Noise marker present → NOISE
      2. Deployment without causal label → CORRELATED (not CAUSAL)
      3. Alert or topology_change → CAUSAL candidate (confidence 0.70)
      4. Metric or log with critical/error severity → CORRELATED (confidence 0.60)
      5. Metric or log with info severity → NOISE (confidence 0.50)
      6. Anything else → AMBIGUOUS
    """

    def disambiguate(
        self,
        events: list[dict[str, Any]],
        causal_incident_id: str | None = None,
    ) -> DisambiguationResult:
        """
        Classify each event in the stream.

        causal_incident_id: if provided, events tagged with this incident_id
        receive higher causal confidence.
        """
        causal: list[ClassifiedSignal] = []
        correlated: list[ClassifiedSignal] = []
        noise: list[ClassifiedSignal] = []
        ambiguous: list[ClassifiedSignal] = []

        for ev in events:
            classified = self._classify(ev, causal_incident_id)
            if classified.signal_class == SignalClass.CAUSAL:
                causal.append(classified)
            elif classified.signal_class == SignalClass.CORRELATED:
                correlated.append(classified)
            elif classified.signal_class == SignalClass.NOISE:
                noise.append(classified)
            else:
                ambiguous.append(classified)

        clarity = self._clarity_score(causal, ambiguous, len(events))
        return DisambiguationResult(
            causal=causal,
            correlated=correlated,
            noise=noise,
            ambiguous=ambiguous,
            causal_clarity_score=clarity,
        )

    def _classify(
        self,
        ev: dict[str, Any],
        causal_incident_id: str | None,
    ) -> ClassifiedSignal:
        event_id = ev.get("event_id", "unknown")
        kind = ev.get("kind", "")
        severity = ev.get("severity", "info")
        is_noise_marker = bool(ev.get(_NOISE_MARKER))
        ev_incident_id = ev.get("incident_id") or ev.get("labels", {}).get("concurrent_incident_id")

        # Rule 1: explicit noise marker
        if is_noise_marker:
            return ClassifiedSignal(
                event_id=event_id,
                signal_class=SignalClass.NOISE,
                reason="noise_deployment_marker",
                confidence=0.95,
            )

        # Rule 2: deployments without noise marker → correlated, not causal
        if kind == "deployment":
            return ClassifiedSignal(
                event_id=event_id,
                signal_class=SignalClass.CORRELATED,
                reason="deployment_correlation_not_causation",
                confidence=0.65,
            )

        # Rule 3: alert or topology change → causal candidate
        if kind in _CAUSAL_KINDS:
            conf = 0.80 if ev_incident_id == causal_incident_id else 0.65
            return ClassifiedSignal(
                event_id=event_id,
                signal_class=SignalClass.CAUSAL,
                reason=f"{kind}_causal_candidate",
                confidence=conf,
            )

        # Rule 4: log/metric with elevated severity → correlated
        if kind in _CORRELATED_KINDS and severity not in _NEUTRAL_SEVERITIES:
            return ClassifiedSignal(
                event_id=event_id,
                signal_class=SignalClass.CORRELATED,
                reason=f"{kind}_elevated_severity_correlation",
                confidence=0.60,
            )

        # Rule 5: log/metric with neutral severity → noise
        if kind in _CORRELATED_KINDS and severity in _NEUTRAL_SEVERITIES:
            return ClassifiedSignal(
                event_id=event_id,
                signal_class=SignalClass.NOISE,
                reason=f"{kind}_neutral_severity_noise",
                confidence=0.50,
            )

        return ClassifiedSignal(
            event_id=event_id,
            signal_class=SignalClass.AMBIGUOUS,
            reason="unclassifiable_kind",
            confidence=0.30,
        )

    @staticmethod
    def _clarity_score(
        causal: list[ClassifiedSignal],
        ambiguous: list[ClassifiedSignal],
        total: int,
    ) -> float:
        if total == 0:
            return 0.0
        # Score degrades with ambiguous signals and lack of causal evidence
        ambiguous_penalty = len(ambiguous) / total
        causal_fraction = len(causal) / total if causal else 0.0
        score = max(0.0, causal_fraction - ambiguous_penalty * 0.5)
        return round(min(1.0, score), 4)
