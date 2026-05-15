"""
Explainability Quality Scoring for SentinelOps Phase 49.

Measures how well an AI-generated incident narrative is explained to operators:
  - Traceability  — evidence is cited per claim
  - Honesty       — uncertainty is acknowledged, not hidden
  - Readability   — technical jargon density penalised
  - Contradiction awareness — contradictions are surfaced, not buried
  - Causal specificity      — causal chain is precise, not hand-wavy
  - Rationale completeness  — all key reasoning steps present

ExplainabilityQualityAnalyzer produces an ExplainabilityScore per incident.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Jargon dictionary (lower-cased multi-word tokens are matched as substrings)
# ---------------------------------------------------------------------------
_JARGON_TERMS: list[str] = [
    "mttr",
    "p99",
    "latency spike",
    "cascading failure",
    "thundering herd",
    "circuit breaker",
    "backpressure",
    "oom",
    "oomkill",
    "cpu throttling",
]

# Phrases that suggest a causal assertion in a sentence.
_CAUSAL_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\bbecause\b", re.IGNORECASE),
    re.compile(r"\bcaused by\b", re.IGNORECASE),
    re.compile(r"\bdue to\b", re.IGNORECASE),
    re.compile(r"\bresulted in\b", re.IGNORECASE),
    re.compile(r"\btherefore\b", re.IGNORECASE),
    re.compile(r"\bconsequently\b", re.IGNORECASE),
    re.compile(r"\bleading to\b", re.IGNORECASE),
    re.compile(r"\btriggered by\b", re.IGNORECASE),
]


@dataclass
class ExplainabilityScore:
    """Per-incident explainability quality score."""

    incident_id: str
    traceability_score: float  # 0.0–1.0: evidence cited per claim
    honesty_score: float  # 0.0–1.0: uncertainty acknowledged
    readability_score: float  # 0.0–1.0: low jargon density is good
    contradiction_awareness: float  # 0.0–1.0: contradictions surfaced
    causal_specificity: float  # 0.0–1.0: causal chain precision
    unsupported_claims: int  # count of causal claims without evidence
    jargon_density: float  # 0.0–1.0 (high = bad)
    rationale_completeness: float  # 0.0–1.0
    overall_explainability_score: float  # weighted average


class ExplainabilityQualityAnalyzer:
    """
    Scores the explainability of an AI-generated incident narrative.

    Usage::

        analyzer = ExplainabilityQualityAnalyzer()
        score = analyzer.score(
            incident_id="inc-001",
            narrative="The service degraded because of an OOMKill ...",
            evidence_refs=["ref-1", "ref-2"],
            confidence=0.72,
            uncertainty_flags=["memory metrics incomplete"],
            contradictions=["some metrics show stable, others degrading"],
        )
    """

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def score(
        self,
        incident_id: str,
        narrative: str,
        evidence_refs: list[str],
        confidence: float,
        uncertainty_flags: list[str],
        contradictions: list[str],
    ) -> ExplainabilityScore:
        """
        Compute an ExplainabilityScore for the given narrative.

        Parameters
        ----------
        incident_id:
            Unique identifier for the incident being scored.
        narrative:
            Full text of the AI-generated incident narrative.
        evidence_refs:
            List of evidence reference identifiers cited in the narrative.
        confidence:
            Model's stated confidence in its root-cause assessment (0.0–1.0).
        uncertainty_flags:
            List of uncertainty signals the model identified and reported.
        contradictions:
            List of contradiction descriptions the model acknowledged.
        """
        narrative_lower = narrative.lower()

        # ---- Traceability -----------------------------------------------
        # Reward: at least one evidence ref per causal sentence.
        causal_sentence_count = self._count_causal_sentences(narrative)
        if causal_sentence_count == 0:
            traceability = 1.0  # no causal claims → nothing to trace
        else:
            cited_refs = len(evidence_refs)
            # Each evidence ref can cover at most one causal sentence.
            traceability = min(1.0, cited_refs / causal_sentence_count)

        # ---- Honesty (uncertainty acknowledged) -------------------------
        # High confidence with no uncertainty flags → lower honesty score.
        if confidence >= 0.90 and len(uncertainty_flags) == 0:
            honesty = 0.20
        elif confidence >= 0.75 and len(uncertainty_flags) == 0:
            honesty = 0.50
        elif len(uncertainty_flags) > 0:
            # Scale with number of flags (more flags = more honest), cap at 1.0
            honesty = min(1.0, 0.60 + 0.20 * len(uncertainty_flags))
        else:
            honesty = 0.80  # modest confidence with no flags — acceptable

        # ---- Readability (jargon penalty) --------------------------------
        jargon = self._jargon_density(narrative)
        readability = max(0.0, 1.0 - jargon)

        # ---- Contradiction awareness ------------------------------------
        if contradictions:
            # Each contradiction acknowledged earns 0.33, capped at 1.0
            contradiction_awareness = min(1.0, 0.40 + 0.30 * len(contradictions))
        else:
            # No contradictions → neutral; if narrative itself shows contrasting
            # terms without acknowledgment, score is reduced slightly.
            has_implicit = self._has_unacknowledged_contradiction(narrative_lower)
            contradiction_awareness = 0.60 if has_implicit else 1.0

        # ---- Causal specificity -----------------------------------------
        # Penalise vague causal language ("might", "possibly", "could be").
        vague_count = self._count_vague_causal_terms(narrative_lower)
        causal_specificity = max(0.0, 1.0 - 0.20 * vague_count)

        # ---- Unsupported claims -----------------------------------------
        unsupported = self._detect_unsupported_claims(narrative, evidence_refs)

        # ---- Rationale completeness -------------------------------------
        # Full score requires: evidence refs, uncertainty flags, causal claims.
        rationale_parts = [
            len(evidence_refs) > 0,
            causal_sentence_count > 0,
            len(uncertainty_flags) > 0 or confidence <= 0.60,
        ]
        rationale_completeness = sum(rationale_parts) / len(rationale_parts)

        # ---- Overall weighted average -----------------------------------
        overall = self._overall_score(
            traceability=traceability,
            honesty=honesty,
            readability=readability,
            contradiction_awareness=contradiction_awareness,
            causal_specificity=causal_specificity,
            rationale_completeness=rationale_completeness,
        )

        return ExplainabilityScore(
            incident_id=incident_id,
            traceability_score=round(traceability, 4),
            honesty_score=round(honesty, 4),
            readability_score=round(readability, 4),
            contradiction_awareness=round(contradiction_awareness, 4),
            causal_specificity=round(causal_specificity, 4),
            unsupported_claims=unsupported,
            jargon_density=round(jargon, 4),
            rationale_completeness=round(rationale_completeness, 4),
            overall_explainability_score=round(overall, 4),
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _detect_unsupported_claims(self, narrative: str, evidence_refs: list[str]) -> int:
        """
        Count sentences that assert causation but have no matching evidence ref.

        A sentence is considered causal if it contains a causal pattern keyword.
        A sentence is considered supported if at least one evidence_ref token
        appears anywhere in the sentence (case-insensitive match).
        """
        sentences = re.split(r"(?<=[.!?])\s+", narrative.strip())
        unsupported = 0
        ref_set = {r.lower() for r in evidence_refs}

        for sentence in sentences:
            sentence_lower = sentence.lower()
            is_causal = any(p.search(sentence) for p in _CAUSAL_PATTERNS)
            if not is_causal:
                continue
            # Check if any evidence ref appears in the sentence.
            has_support = any(ref in sentence_lower for ref in ref_set)
            if not has_support:
                unsupported += 1

        return unsupported

    def _jargon_density(self, narrative: str) -> float:
        """
        Compute the ratio of jargon-matched tokens to total whitespace-split tokens.

        Multi-word jargon terms (e.g. "latency spike") are matched as substrings
        first; single-word terms are compared against individual tokens.  The
        result is clipped to [0.0, 1.0].
        """
        if not narrative.strip():
            return 0.0

        narrative_lower = narrative.lower()
        tokens = narrative_lower.split()
        total_tokens = len(tokens)
        if total_tokens == 0:
            return 0.0

        jargon_token_count = 0

        for term in _JARGON_TERMS:
            term_tokens = term.split()
            if len(term_tokens) > 1:
                # Multi-word: count non-overlapping occurrences, each worth
                # len(term_tokens) jargon tokens.
                pattern = re.compile(re.escape(term))
                matches = pattern.findall(narrative_lower)
                jargon_token_count += len(matches) * len(term_tokens)
            else:
                # Single-word: count exact token matches.
                jargon_token_count += tokens.count(term)

        return min(1.0, jargon_token_count / total_tokens)

    @staticmethod
    def _count_causal_sentences(narrative: str) -> int:
        sentences = re.split(r"(?<=[.!?])\s+", narrative.strip())
        return sum(1 for s in sentences if any(p.search(s) for p in _CAUSAL_PATTERNS))

    @staticmethod
    def _count_vague_causal_terms(narrative_lower: str) -> int:
        vague_terms = [
            r"\bmight\b",
            r"\bpossibly\b",
            r"\bcould be\b",
            r"\bperhaps\b",
            r"\bmaybe\b",
            r"\bseems to\b",
            r"\bappears to\b",
        ]
        count = 0
        for pattern in vague_terms:
            count += len(re.findall(pattern, narrative_lower))
        return count

    @staticmethod
    def _has_unacknowledged_contradiction(narrative_lower: str) -> bool:
        antonym_pairs = [
            ("resolved", "unresolved"),
            ("stable", "degrading"),
            ("healthy", "unhealthy"),
            ("improving", "worsening"),
        ]
        for a, b in antonym_pairs:
            if a in narrative_lower and b in narrative_lower:
                return True
        return False

    @staticmethod
    def _overall_score(
        *,
        traceability: float,
        honesty: float,
        readability: float,
        contradiction_awareness: float,
        causal_specificity: float,
        rationale_completeness: float,
    ) -> float:
        """
        Weighted average:
          0.25 traceability
          0.20 honesty
          0.15 readability
          0.15 contradiction_awareness
          0.15 causal_specificity
          0.10 rationale_completeness
        """
        return (
            0.25 * traceability
            + 0.20 * honesty
            + 0.15 * readability
            + 0.15 * contradiction_awareness
            + 0.15 * causal_specificity
            + 0.10 * rationale_completeness
        )
