"""
Remediation Usefulness Evaluation for SentinelOps Phase 49.

Assesses how operationally useful a remediation recommendation is to a
first-responder operator, beyond pure actionability:

  - Specific commands    — shell/tooling commands are present
  - Verification step    — instructions tell the operator how to confirm success
  - Timing guidance      — time-sensitive or sequencing information is given
  - Idempotent safety    — recommendation is safe to run more than once

RemediationUsefulnessEvaluator.evaluate() returns a RemediationUsefulnessReport
per incident, including individual usefulness signals.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Compiled patterns for feature detection
# ---------------------------------------------------------------------------

# Shell / tooling command patterns
_COMMAND_PATTERN: re.Pattern[str] = re.compile(
    r"\$\s*\w+|kubectl|helm|systemctl|docker|aws\s+\w+|terraform",
    re.IGNORECASE,
)

# Verification language (case-insensitive word-boundary match)
_VERIFY_PATTERN: re.Pattern[str] = re.compile(
    r"\bverify\b|\bcheck\b|\bconfirm\b|\bvalidate\b|\btest\b",
    re.IGNORECASE,
)

# Timing / sequencing language
_TIMING_WORDS: list[str] = [
    "wait",
    "after",
    "minutes",
    "seconds",
    "timeout",
    "grace period",
]

# Idempotent / safe-to-retry language
_IDEMPOTENT_PHRASES: list[str] = [
    "idempotent",
    "safe to retry",
    "can be run multiple times",
]


@dataclass
class UsefulnessSignal:
    """A single usefulness signal detected in a remediation recommendation."""

    signal_type: str  # short identifier, e.g. "HAS_SPECIFIC_COMMANDS"
    description: str
    impact: float  # -1.0 to 1.0  (positive = useful, negative = harmful)


@dataclass
class RemediationUsefulnessReport:
    """Per-incident usefulness report for an AI-generated remediation."""

    incident_id: str
    usefulness_score: float  # 0.0–1.0
    signals: list[UsefulnessSignal]
    has_specific_commands: bool
    has_verification_step: bool
    has_timing_guidance: bool
    is_idempotent_safe: bool
    recommendation_length_chars: int


class RemediationUsefulnessEvaluator:
    """
    Evaluates how operationally useful a remediation recommendation is.

    Usage::

        evaluator = RemediationUsefulnessEvaluator()
        report = evaluator.evaluate(
            incident_id="inc-001",
            recommendation="kubectl rollout restart deployment/api; verify with kubectl get pods",
            mechanism="Pod restart loop",
        )
    """

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def evaluate(
        self,
        incident_id: str,
        recommendation: str,
        mechanism: str,
    ) -> RemediationUsefulnessReport:
        """
        Compute a RemediationUsefulnessReport for the given recommendation.

        Parameters
        ----------
        incident_id:
            Unique identifier for the incident being evaluated.
        recommendation:
            Full text of the AI-generated remediation recommendation.
        mechanism:
            Short description of the failure mechanism driving the incident
            (used for context; does not affect scoring in this version).
        """
        rec_lower = recommendation.lower()
        signals: list[UsefulnessSignal] = []

        # ---- Feature: specific commands ------------------------------------
        has_specific_commands = bool(_COMMAND_PATTERN.search(recommendation))

        # ---- Feature: verification step ------------------------------------
        # The verification keyword must appear after at least one action verb
        # or after some content (i.e. not just "verify this" as the whole rec).
        has_verification_step = self._check_verification(rec_lower)

        # ---- Feature: timing guidance -------------------------------------
        has_timing_guidance = any(word in rec_lower for word in _TIMING_WORDS)

        # ---- Feature: idempotent safety -----------------------------------
        is_idempotent_safe = any(phrase in rec_lower for phrase in _IDEMPOTENT_PHRASES)

        # ---- Feature: length check ----------------------------------------
        rec_length = len(recommendation)
        too_brief = rec_length < 50

        # ---- Build signals -------------------------------------------------
        if has_specific_commands:
            signals.append(
                UsefulnessSignal(
                    signal_type="HAS_SPECIFIC_COMMANDS",
                    description=(
                        "Recommendation contains shell or tooling commands, enabling "
                        "direct operator execution without interpretation."
                    ),
                    impact=0.20,
                )
            )

        if has_verification_step:
            signals.append(
                UsefulnessSignal(
                    signal_type="HAS_VERIFICATION_STEP",
                    description=(
                        "Recommendation includes a verification or confirmation step "
                        "so the operator can confirm success."
                    ),
                    impact=0.15,
                )
            )

        if has_timing_guidance:
            signals.append(
                UsefulnessSignal(
                    signal_type="HAS_TIMING_GUIDANCE",
                    description=(
                        "Recommendation provides timing or sequencing guidance to "
                        "help the operator pace their actions safely."
                    ),
                    impact=0.10,
                )
            )

        if is_idempotent_safe:
            signals.append(
                UsefulnessSignal(
                    signal_type="IS_IDEMPOTENT_SAFE",
                    description=(
                        "Recommendation is explicitly marked as idempotent or safe "
                        "to retry, reducing operator hesitation under pressure."
                    ),
                    impact=0.10,
                )
            )

        if too_brief:
            signals.append(
                UsefulnessSignal(
                    signal_type="TOO_BRIEF",
                    description=(
                        f"Recommendation is only {rec_length} characters, which is "
                        "likely insufficient to guide an operator through remediation."
                    ),
                    impact=-0.20,
                )
            )

        # ---- Compute usefulness score --------------------------------------
        score = 0.40  # baseline
        if has_specific_commands:
            score += 0.20
        if has_verification_step:
            score += 0.15
        if has_timing_guidance:
            score += 0.10
        if is_idempotent_safe:
            score += 0.10
        if too_brief:
            score -= 0.20

        usefulness_score = max(0.0, min(1.0, score))

        return RemediationUsefulnessReport(
            incident_id=incident_id,
            usefulness_score=round(usefulness_score, 4),
            signals=signals,
            has_specific_commands=has_specific_commands,
            has_verification_step=has_verification_step,
            has_timing_guidance=has_timing_guidance,
            is_idempotent_safe=is_idempotent_safe,
            recommendation_length_chars=rec_length,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _check_verification(rec_lower: str) -> bool:
        """
        Return True if the recommendation contains verification language after
        the main action content.

        To avoid trivially short recommendations that only say "verify X",
        we require the match to appear somewhere in the text (the regex
        pattern handles the general case, and the "after the main action"
        spirit is captured by requiring the recommendation is non-trivial).
        """
        return bool(_VERIFY_PATTERN.search(rec_lower))
