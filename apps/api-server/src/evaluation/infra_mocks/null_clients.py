"""
Null external service clients for EVALUATION execution mode.

These replace live Qdrant, Prometheus, Loki, and GitHub clients during
evaluation. They return empty results without making any network calls,
enforcing the zero-external-side-effects requirement.
"""
from __future__ import annotations

from typing import Any


class NullIncidentHistorySearcher:
    """
    Returns empty similar incidents without querying Qdrant.

    Passed to classify_incident() as the searcher= parameter to prevent
    any Qdrant connection during evaluation replay.
    """

    async def search_similar_incidents(self, text: str, limit: int = 3) -> list[dict[str, Any]]:
        return []

    async def close(self) -> None:
        pass


class NullPatternSearcher:
    """
    Returns empty pattern hints without querying Qdrant.

    Passed to analyze_root_cause() as the pattern_searcher= parameter
    to prevent any Qdrant connection during evaluation replay.
    """

    def search(self, text: str, limit: int = 3) -> list[dict[str, Any]]:
        return []
