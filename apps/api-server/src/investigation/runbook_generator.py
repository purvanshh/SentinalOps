"""
Dynamic Runbook Generation for SentinelOps Phase 13 (numbered as Phase 12 commit).

Instead of stopping at "Root Cause: X", generate actionable investigation
and remediation plans:

    Diagnosis → Investigation Plan → Fix Plan → Rollback Plan →
    Verification Checklist → Monitoring Plan

This makes SentinelOps useful, not just intelligent.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class RunbookStep:
    """A single step in a generated runbook."""

    step_number: int
    action: str
    command: str = ""
    expected_outcome: str = ""
    rollback_if_failed: str = ""
    estimated_minutes: float = 1.0


@dataclass
class GeneratedRunbook:
    """Complete dynamically generated runbook for incident remediation."""

    incident_id: str
    root_cause: str
    mechanism_type: str
    affected_service: str
    confidence: float

    diagnosis_steps: List[RunbookStep] = field(default_factory=list)
    investigation_steps: List[RunbookStep] = field(default_factory=list)
    fix_steps: List[RunbookStep] = field(default_factory=list)
    rollback_steps: List[RunbookStep] = field(default_factory=list)
    verification_steps: List[RunbookStep] = field(default_factory=list)
    monitoring_steps: List[RunbookStep] = field(default_factory=list)

    @property
    def total_estimated_minutes(self) -> float:
        all_steps = (
            self.diagnosis_steps + self.investigation_steps +
            self.fix_steps + self.rollback_steps +
            self.verification_steps + self.monitoring_steps
        )
        return sum(s.estimated_minutes for s in all_steps)

    def to_markdown(self) -> str:
        """Render the runbook as markdown for operator consumption."""
        lines = [
            f"# Runbook: {self.root_cause}",
            f"**Service:** {self.affected_service}  ",
            f"**Mechanism:** {self.mechanism_type}  ",
            f"**Confidence:** {self.confidence:.0%}  ",
            f"**Estimated Time:** {self.total_estimated_minutes:.0f} minutes",
            "",
        ]

        sections = [
            ("## 1. Diagnosis", self.diagnosis_steps),
            ("## 2. Investigation", self.investigation_steps),
            ("## 3. Fix", self.fix_steps),
            ("## 4. Rollback Plan", self.rollback_steps),
            ("## 5. Verification", self.verification_steps),
            ("## 6. Post-Fix Monitoring", self.monitoring_steps),
        ]

        for header, steps in sections:
            if steps:
                lines.append(header)
                for step in steps:
                    lines.append(f"{step.step_number}. {step.action}")
                    if step.command:
                        lines.append(f"   ```\n   {step.command}\n   ```")
                    if step.expected_outcome:
                        lines.append(f"   Expected: {step.expected_outcome}")
                lines.append("")

        return "\n".join(lines)


# Template runbook fragments by mechanism type
_MECHANISM_TEMPLATES: Dict[str, Dict[str, List[Dict[str, str]]]] = {
    "deployment_error": {
        "diagnosis": [
            {"action": "Identify the deployment that preceded the incident",
             "command": "kubectl rollout history deployment/{service}"},
            {"action": "Compare configuration diff between versions",
             "command": (
                 "diff <(kubectl get configmap {service}-config -o yaml"
                 " --revision=prev)"
                 " <(kubectl get configmap {service}-config -o yaml)"
             )},
        ],
        "fix": [
            {"action": "Rollback to the last known good deployment",
             "command": "kubectl rollout undo deployment/{service}"},
            {"action": "Verify service health after rollback",
             "command": "curl -s http://{service}/healthz"},
        ],
        "rollback": [
            {"action": "If rollback worsens the issue, re-deploy current version",
             "command": "kubectl rollout undo deployment/{service}"},
        ],
        "verification": [
            {"action": "Verify error rates returned to baseline", "command": ""},
            {"action": "Check that latency p99 is within SLO", "command": ""},
        ],
    },
    "resource_exhaustion": {
        "diagnosis": [
            {"action": "Check current resource utilization",
             "command": "kubectl top pods -l app={service}"},
            {"action": "Review memory and CPU trends", "command": ""},
        ],
        "fix": [
            {"action": "Increase resource limits or restart pods",
             "command": "kubectl rollout restart deployment/{service}"},
            {"action": "If memory leak suspected, capture heap dump first", "command": ""},
        ],
        "verification": [
            {"action": "Monitor resource usage for 15 minutes post-fix", "command": ""},
            {"action": "Verify no OOM kills in pod events",
             "command": "kubectl get events --field-selector reason=OOMKilling"},
        ],
    },
    "configuration_drift": {
        "diagnosis": [
            {"action": "Compare current config against baseline", "command": ""},
            {"action": "Check environment variable changes", "command": ""},
        ],
        "fix": [
            {"action": "Restore configuration to last known good state", "command": ""},
            {"action": "Restart affected services",
             "command": "kubectl rollout restart deployment/{service}"},
        ],
        "verification": [
            {"action": "Verify configuration values match expected baseline", "command": ""},
        ],
    },
    "dependency_failure": {
        "diagnosis": [
            {"action": "Check health of upstream dependencies", "command": ""},
            {"action": "Review connection pool metrics", "command": ""},
            {"action": "Check DNS resolution for dependency endpoints",
             "command": "nslookup {dependency}"},
        ],
        "fix": [
            {"action": "If dependency is external, enable circuit breaker", "command": ""},
            {"action": "If DNS issue, flush resolver cache", "command": ""},
        ],
        "verification": [
            {"action": "Verify dependency health endpoint is responding", "command": ""},
            {"action": "Observe latency returning to baseline", "command": ""},
        ],
    },
    "cascade_failure": {
        "diagnosis": [
            {"action": "Identify the originating service in the failure cascade", "command": ""},
            {"action": "Map affected downstream services", "command": ""},
        ],
        "fix": [
            {"action": "Fix the originating service first", "command": ""},
            {"action": "Restart downstream services in dependency order", "command": ""},
        ],
        "verification": [
            {"action": "Verify all services in the cascade are healthy", "command": ""},
        ],
    },
}


class RunbookGenerator:
    """
    Generates actionable runbooks from root cause analysis results.

    Uses mechanism-specific templates to produce structured investigation
    and remediation plans. Each runbook includes diagnosis, fix, rollback,
    verification, and monitoring phases.
    """

    def generate(
        self,
        incident_id: str,
        root_cause: str,
        mechanism_type: str,
        affected_service: str,
        confidence: float,
    ) -> GeneratedRunbook:
        """Generate a complete runbook for the identified root cause."""
        templates = _MECHANISM_TEMPLATES.get(
            mechanism_type, _MECHANISM_TEMPLATES.get("dependency_failure", {})
        )

        def build_steps(phase: str) -> List[RunbookStep]:
            steps = []
            for i, tmpl in enumerate(templates.get(phase, []), 1):
                action = tmpl["action"].replace("{service}", affected_service)
                command = tmpl.get("command", "").replace("{service}", affected_service)
                steps.append(RunbookStep(
                    step_number=i,
                    action=action,
                    command=command,
                    estimated_minutes=2.0,
                ))
            return steps

        # Always add a monitoring step
        monitoring = [
            RunbookStep(
                step_number=1,
                action=f"Monitor {affected_service} error rates and latency for 30 minutes",
                estimated_minutes=30.0,
            ),
            RunbookStep(
                step_number=2,
                action="Confirm no recurrence of the original alert condition",
                estimated_minutes=5.0,
            ),
        ]

        return GeneratedRunbook(
            incident_id=incident_id,
            root_cause=root_cause,
            mechanism_type=mechanism_type,
            affected_service=affected_service,
            confidence=confidence,
            diagnosis_steps=build_steps("diagnosis"),
            investigation_steps=build_steps("investigation"),
            fix_steps=build_steps("fix"),
            rollback_steps=build_steps("rollback"),
            verification_steps=build_steps("verification"),
            monitoring_steps=monitoring,
        )
