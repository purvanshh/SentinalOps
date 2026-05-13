"""
Evaluation trace capture for benchmark replay runs.

Each benchmark replay persists an EvaluationTrace containing the full
execution details. These are stored separately from production incident
traces and enable regression analysis across releases.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class EvaluationTrace:
    """
    Full execution trace for a single benchmark incident replay.

    Captured during run_agent_pipeline() and persisted separately from
    production incident state for cross-release regression analysis.
    """

    benchmark_id: str
    execution_id: str
    thread_id: str
    started_at: float = field(default_factory=time.time)
    completed_at: float | None = None

    state_snapshots: list[dict[str, Any]] = field(default_factory=list)
    agent_outputs: dict[str, Any] = field(default_factory=dict)
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    reasoning_summaries: dict[str, str] = field(default_factory=dict)
    timing: dict[str, float] = field(default_factory=dict)
    failures: list[str] = field(default_factory=list)
    hallucination_detections: list[str] = field(default_factory=list)
    confidence_scores: dict[str, float] = field(default_factory=dict)

    @property
    def duration_seconds(self) -> float | None:
        if self.completed_at is None:
            return None
        return self.completed_at - self.started_at

    def record_agent_output(self, agent_name: str, output: Any) -> None:
        if hasattr(output, "model_dump"):
            self.agent_outputs[agent_name] = output.model_dump(mode="json")
        else:
            self.agent_outputs[agent_name] = output

    def record_timing(self, step: str, elapsed: float) -> None:
        self.timing[step] = round(elapsed, 4)

    def to_dict(self) -> dict[str, Any]:
        return {
            "benchmark_id": self.benchmark_id,
            "execution_id": self.execution_id,
            "thread_id": self.thread_id,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "duration_seconds": self.duration_seconds,
            "agent_outputs": self.agent_outputs,
            "tool_calls": self.tool_calls,
            "reasoning_summaries": self.reasoning_summaries,
            "timing": self.timing,
            "failures": self.failures,
            "hallucination_detections": self.hallucination_detections,
            "confidence_scores": self.confidence_scores,
        }
