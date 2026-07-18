"""
Autonomous Investigation Planner for SentinelOps Phase 14.

Instead of reasoning once on available logs, the system decides what
information it needs next and actively seeks it — exactly like a human SRE.

Flow:
    Logs → Need More Information → Ask Metrics Agent →
    Still uncertain → Ask Deployment Agent →
    Still uncertain → Ask Git Agent → Converge

The planner iteratively evaluates uncertainty and dispatches targeted
investigation requests to specialist agents until confidence exceeds
a threshold or all available sources have been exhausted.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List

from agents.specialists import (
    DependencyInvestigator,
    DeploymentInvestigator,
    GitInvestigator,
    MetricsInvestigator,
    RunbookInvestigator,
    SpecialistFinding,
    TopologyInvestigator,
)


@dataclass
class InvestigationStep:
    """Records a single step in the autonomous investigation."""

    step_number: int
    agent_queried: str
    question: str
    finding: SpecialistFinding | None = None
    confidence_before: float = 0.0
    confidence_after: float = 0.0
    information_gain: float = 0.0
    decision: str = ""  # "continue" | "converge" | "escalate"


@dataclass
class InvestigationPlan:
    """Complete investigation plan with all steps and final decision."""

    incident_id: str
    service: str
    steps: List[InvestigationStep] = field(default_factory=list)
    final_confidence: float = 0.0
    final_hypothesis: str = ""
    final_mechanism: str = ""
    converged: bool = False
    escalated: bool = False
    sources_exhausted: bool = False

    @property
    def total_steps(self) -> int:
        return len(self.steps)

    @property
    def agents_consulted(self) -> List[str]:
        return [s.agent_queried for s in self.steps]

    def to_dict(self) -> dict[str, Any]:
        return {
            "incident_id": self.incident_id,
            "service": self.service,
            "total_steps": self.total_steps,
            "final_confidence": self.final_confidence,
            "final_hypothesis": self.final_hypothesis,
            "final_mechanism": self.final_mechanism,
            "converged": self.converged,
            "escalated": self.escalated,
            "agents_consulted": self.agents_consulted,
        }


# Investigation priority order — most informative sources first
_INVESTIGATION_PRIORITY = [
    ("metrics_investigator", MetricsInvestigator, "What metric anomalies are present?"),
    ("deployment_investigator", DeploymentInvestigator, "Were there recent deployments?"),
    ("dependency_investigator", DependencyInvestigator, "Are upstream dependencies failing?"),
    ("topology_investigator", TopologyInvestigator, "Is this a cascade across services?"),
    ("git_investigator", GitInvestigator, "Were there recent code changes?"),
    ("runbook_investigator", RunbookInvestigator, "Does this match a known failure pattern?"),
]


class AutonomousInvestigationPlanner:
    """
    Iteratively investigates an incident by querying specialist agents
    in priority order until confidence converges or sources are exhausted.

    Convergence criteria:
    - confidence >= convergence_threshold (default 0.75)
    - OR all specialist agents have been consulted
    - OR two consecutive agents add no information gain
    """

    def __init__(
        self,
        convergence_threshold: float = 0.75,
        escalation_threshold: float = 0.30,
        max_steps: int = 8,
    ) -> None:
        self.convergence_threshold = convergence_threshold
        self.escalation_threshold = escalation_threshold
        self.max_steps = max_steps

    def investigate(
        self,
        incident_id: str,
        evidence_items: list[dict[str, Any]],
        service: str = "unknown",
        **context: Any,
    ) -> InvestigationPlan:
        """Run an autonomous investigation, querying agents iteratively."""
        plan = InvestigationPlan(
            incident_id=incident_id,
            service=service,
        )

        current_confidence = 0.0
        best_hypothesis = ""
        best_mechanism = ""
        all_findings: List[SpecialistFinding] = []
        zero_gain_streak = 0

        for step_num, (agent_name, agent_class, question) in enumerate(_INVESTIGATION_PRIORITY, 1):
            if step_num > self.max_steps:
                break

            # Instantiate and run the specialist
            agent = agent_class()
            finding = agent.investigate(evidence_items, service, **context)

            # Calculate information gain
            confidence_before = current_confidence
            if finding.confidence > 0:
                # Bayesian-style update: new confidence = weighted combination
                new_evidence_weight = 0.3
                current_confidence = (
                    current_confidence * (1 - new_evidence_weight) +
                    finding.confidence * new_evidence_weight
                )
                current_confidence = min(1.0, current_confidence)

                best_conf = getattr(all_findings[0], "confidence", 0) if all_findings else 0
                if finding.confidence > best_conf:
                    best_hypothesis = finding.hypothesis
                    best_mechanism = finding.mechanism_type

                all_findings.append(finding)
                zero_gain_streak = 0
            else:
                zero_gain_streak += 1

            information_gain = current_confidence - confidence_before

            # Decide whether to continue, converge, or escalate
            if current_confidence >= self.convergence_threshold:
                decision = "converge"
            elif zero_gain_streak >= 2:
                decision = "converge"
            elif step_num == len(_INVESTIGATION_PRIORITY):
                decision = "converge"
            else:
                decision = "continue"

            step = InvestigationStep(
                step_number=step_num,
                agent_queried=agent_name,
                question=question,
                finding=finding if finding.confidence > 0 else None,
                confidence_before=round(confidence_before, 4),
                confidence_after=round(current_confidence, 4),
                information_gain=round(information_gain, 4),
                decision=decision,
            )
            plan.steps.append(step)

            if decision == "converge":
                break

        # Final assessment
        plan.final_confidence = round(current_confidence, 4)
        plan.final_hypothesis = best_hypothesis
        plan.final_mechanism = best_mechanism

        if current_confidence >= self.convergence_threshold:
            plan.converged = True
        elif current_confidence <= self.escalation_threshold and all_findings:
            plan.escalated = True
        else:
            plan.sources_exhausted = True

        return plan
