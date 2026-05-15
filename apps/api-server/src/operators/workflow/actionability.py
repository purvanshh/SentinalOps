"""
Recommendation Actionability Analysis for SentinelOps Phase 49.

Measures how operationally actionable an AI-generated remediation recommendation
is before it is surfaced to an operator under incident pressure:

  - Clarity                — recommendation language is unambiguous
  - Operational specificity — concrete steps are present, not hand-wavy guidance
  - Execution feasibility  — the recommended action can plausibly be executed
  - Rollback preparedness  — a rollback path is defined and non-trivial
  - Dependency awareness   — external dependencies are acknowledged
  - Safety explicitness    — blast radius and risk are stated explicitly

ActionabilityAnalyzer.analyze() returns an ActionabilityScore per incident.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

# ---------------------------------------------------------------------------
# Vague operational phrases that lower clarity and specificity
# ---------------------------------------------------------------------------
_VAGUE_PHRASES: list[str] = [
    "investigate further",
    "check logs",
    "monitor the situation",
    "look into",
    "consider restarting",
    "may need to",
    "might be",
    "could potentially",
]

# Regex to detect numbered steps (e.g. "1.", "Step 3")
_STEP_NUMBER_PATTERN: re.Pattern[str] = re.compile(r"\d+\.|\bstep \d+\b", re.IGNORECASE)


class ActionabilityClass(Enum):
    """Operational classification of a recommendation's actionability."""

    HIGHLY_ACTIONABLE = "HIGHLY_ACTIONABLE"
    ACTIONABLE = "ACTIONABLE"
    PARTIALLY_ACTIONABLE = "PARTIALLY_ACTIONABLE"
    OPERATIONALLY_VAGUE = "OPERATIONALLY_VAGUE"
    DANGEROUSLY_AMBIGUOUS = "DANGEROUSLY_AMBIGUOUS"


@dataclass
class ActionabilityScore:
    """Per-incident actionability score for an AI-generated recommendation."""

    incident_id: str
    clarity: float  # 0.0–1.0
    operational_specificity: float  # 0.0–1.0
    execution_feasibility: float  # 0.0–1.0
    rollback_preparedness: float  # 0.0–1.0
    dependency_awareness: float  # 0.0–1.0
    safety_explicitness: float  # 0.0–1.0
    ambiguity_penalty: float  # 0.0–1.0  (higher = more penalty)
    overall_actionability: float  # weighted composite
    actionability_class: ActionabilityClass


class ActionabilityAnalyzer:
    """
    Scores the operational actionability of an AI-generated remediation
    recommendation.

    Usage::

        analyzer = ActionabilityAnalyzer()
        score = analyzer.analyze(
            incident_id="inc-001",
            recommendation="Step 1. kubectl rollout restart deployment/api ...",
            rollback_plan="kubectl rollout undo deployment/api",
            dependencies=["database", "cache"],
            blast_radius_mentioned=True,
        )
    """

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze(
        self,
        incident_id: str,
        recommendation: str,
        rollback_plan: str | None,
        dependencies: list[str],
        blast_radius_mentioned: bool,
    ) -> ActionabilityScore:
        """
        Compute an ActionabilityScore for the given recommendation.

        Parameters
        ----------
        incident_id:
            Unique identifier for the incident being scored.
        recommendation:
            Full text of the AI-generated remediation recommendation.
        rollback_plan:
            Text describing the rollback procedure, or None if absent.
        dependencies:
            List of external dependency names acknowledged in context.
        blast_radius_mentioned:
            True if the recommendation or its context explicitly states the
            blast radius or scope of impact.
        """
        rec_lower = recommendation.lower()

        # ---- Vague pattern penalty (shared across clarity + specificity) ---
        vague_penalty = self._detect_vague_patterns(recommendation)

        # ---- Clarity -------------------------------------------------------
        # High clarity means low vague language; also reward numbered steps.
        has_steps = bool(_STEP_NUMBER_PATTERN.search(recommendation))
        clarity = max(0.0, 1.0 - vague_penalty)
        if has_steps:
            clarity = min(1.0, clarity + 0.10)

        # ---- Operational specificity ---------------------------------------
        # Specific recommendations reference concrete tooling or actions.
        specificity_signals = [
            bool(
                re.search(
                    r"\$\s*\w+|kubectl|helm|systemctl|docker|aws\s+\w+|terraform",
                    recommendation,
                )
            ),
            has_steps,
            len(recommendation) >= 100,
        ]
        operational_specificity = max(
            0.0, (sum(specificity_signals) / len(specificity_signals)) - vague_penalty * 0.5
        )
        operational_specificity = min(1.0, operational_specificity)

        # ---- Execution feasibility -----------------------------------------
        # Feasibility is higher when steps are present and the text is long
        # enough to contain real instructions.
        feasibility_base = 0.50
        if has_steps:
            feasibility_base += 0.25
        if len(recommendation) >= 80:
            feasibility_base += 0.15
        if vague_penalty > 0.50:
            feasibility_base -= 0.30
        execution_feasibility = max(0.0, min(1.0, feasibility_base))

        # ---- Rollback preparedness -----------------------------------------
        if rollback_plan is not None and len(rollback_plan) >= 20:
            rollback_preparedness = 1.0
        elif rollback_plan is not None and len(rollback_plan) >= 5:
            rollback_preparedness = 0.40
        else:
            rollback_preparedness = 0.0

        # ---- Dependency awareness ------------------------------------------
        if not dependencies:
            # No dependencies supplied — neutral score
            dependency_awareness = 0.70
        else:
            # Check how many dependencies are actually mentioned in the text
            mentioned = sum(1 for d in dependencies if d.lower() in rec_lower)
            dependency_awareness = min(1.0, mentioned / len(dependencies))

        # ---- Safety explicitness -------------------------------------------
        safety_keywords = [
            "blast radius",
            "impact",
            "risk",
            "caution",
            "warning",
            "rollback",
            "revert",
            "undo",
            "safe",
        ]
        matched_safety = sum(1 for kw in safety_keywords if kw in rec_lower)
        safety_explicitness = min(1.0, matched_safety * 0.15)
        if blast_radius_mentioned:
            safety_explicitness = min(1.0, safety_explicitness + 0.40)

        # ---- Ambiguity penalty (anti-patterns) -----------------------------
        ambiguity_penalty = self._detect_anti_patterns(recommendation, rollback_plan)
        if not blast_radius_mentioned:
            pass  # already included inside _detect_anti_patterns

        # ---- Overall weighted composite ------------------------------------
        raw = (
            0.20 * clarity
            + 0.20 * operational_specificity
            + 0.15 * execution_feasibility
            + 0.15 * rollback_preparedness
            + 0.15 * dependency_awareness
            + 0.15 * safety_explicitness
            - ambiguity_penalty * 0.30
        )
        overall_actionability = max(0.0, min(1.0, raw))

        actionability_class = self._classify(overall_actionability)

        return ActionabilityScore(
            incident_id=incident_id,
            clarity=round(clarity, 4),
            operational_specificity=round(operational_specificity, 4),
            execution_feasibility=round(execution_feasibility, 4),
            rollback_preparedness=round(rollback_preparedness, 4),
            dependency_awareness=round(dependency_awareness, 4),
            safety_explicitness=round(safety_explicitness, 4),
            ambiguity_penalty=round(ambiguity_penalty, 4),
            overall_actionability=round(overall_actionability, 4),
            actionability_class=actionability_class,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _detect_vague_patterns(self, text: str) -> float:
        """
        Return a penalty in [0.0, 1.0] proportional to the number of vague
        operational phrases found in *text*.

        Each distinct vague phrase hit contributes 0.15 to the penalty,
        capped at 1.0.
        """
        text_lower = text.lower()
        hits = sum(1 for phrase in _VAGUE_PHRASES if phrase in text_lower)
        return min(1.0, hits * 0.15)

    def _detect_anti_patterns(
        self,
        recommendation: str,
        rollback_plan: str | None,
    ) -> float:
        """
        Compute an ambiguity penalty in [0.0, 1.0] based on operational
        anti-patterns detected in the recommendation and rollback plan.

        Anti-pattern rules
        ------------------
        +0.25  "restart" mentioned without a conditional ("if" / "when")
        +0.20  rollback_plan is None or shorter than 20 characters
        +0.15  blast_radius_mentioned is False  (checked by caller — passed via
               the *recommendation* text heuristic here)
        +0.10  No step numbers detected (regex: r"\\d+\\.\\|\\bstep \\d+\\b")
        """
        penalty = 0.0
        rec_lower = recommendation.lower()

        # Anti-pattern 1: unconditional restart
        if "restart" in rec_lower:
            has_condition = bool(re.search(r"\bif\b|\bwhen\b", rec_lower))
            if not has_condition:
                penalty += 0.25

        # Anti-pattern 2: missing or trivial rollback plan
        if rollback_plan is None or len(rollback_plan) < 20:
            penalty += 0.20

        # Anti-pattern 3: no blast radius discussion (heuristic on rec text)
        blast_radius_keywords = [
            "blast radius",
            "scope of impact",
            "affected services",
            "downstream",
            "upstream",
            "impact radius",
        ]
        has_blast_radius = any(kw in rec_lower for kw in blast_radius_keywords)
        if not has_blast_radius:
            penalty += 0.15

        # Anti-pattern 4: no step numbers
        if not _STEP_NUMBER_PATTERN.search(recommendation):
            penalty += 0.10

        return min(1.0, penalty)

    @staticmethod
    def _classify(overall: float) -> ActionabilityClass:
        """Map a composite actionability score to an ActionabilityClass."""
        if overall >= 0.80:
            return ActionabilityClass.HIGHLY_ACTIONABLE
        if overall >= 0.60:
            return ActionabilityClass.ACTIONABLE
        if overall >= 0.40:
            return ActionabilityClass.PARTIALLY_ACTIONABLE
        if overall >= 0.20:
            return ActionabilityClass.OPERATIONALLY_VAGUE
        return ActionabilityClass.DANGEROUSLY_AMBIGUOUS
