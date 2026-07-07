from __future__ import annotations

from dataclasses import dataclass

from agents.rootcause_agent.evidence_builder import TimedEvent
from causality.validators.causal_validator import service_exists
from orchestration.state.topology_schema import ServiceNode


@dataclass(slots=True)
class CandidateCause:
    pattern_id: str
    title: str
    cause_service: str
    affected_service: str
    pattern_match_score: float
    required_keywords: list[str]
    supporting_item_keys: list[str]


def _safe_item_key(event: TimedEvent) -> str:
    return event.item_key or "unknown-item"


def _safe_service(event: TimedEvent, default_service: str) -> str:
    return event.service or default_service or "unknown"


def _normalized_text(value: str | None) -> str:
    return (value or "").strip().lower()


def _topology_neighbors(
    service: str,
    topology_graph: dict[str, ServiceNode],
) -> tuple[list[str], list[str]]:
    if not topology_graph or service not in topology_graph:
        return [], []

    upstream = list(topology_graph[service].depends_on)
    downstream = [
        node.name
        for node in topology_graph.values()
        if service in node.depends_on and node.name != service
    ]
    return upstream, downstream


def _metric_candidate(
    event: TimedEvent,
    default_service: str,
) -> CandidateCause:
    payload = event.payload
    service = _safe_service(event, default_service)
    metric_name = payload.get("metric", "")
    observed = payload.get("observed", "")
    metric_lower = _normalized_text(metric_name)

    if "dns" in metric_lower:
        return CandidateCause(
            pattern_id=f"dns_resolution_failure_{service}",
            title=f"{service} DNS resolution failure ({metric_name})",
            cause_service=service,
            affected_service=service,
            pattern_match_score=0.88,
            required_keywords=["dns", "timeout", "resolution"],
            supporting_item_keys=[_safe_item_key(event)],
        )
    if any(token in metric_lower for token in ("external", "third_party", "upstream")):
        return CandidateCause(
            pattern_id=f"external_dependency_degradation_{service}",
            title=f"{service} degraded by external dependency ({metric_name})",
            cause_service=service,
            affected_service=service,
            pattern_match_score=0.87,
            required_keywords=["external", "upstream", "dependency", "latency"],
            supporting_item_keys=[_safe_item_key(event)],
        )
    if any(token in metric_lower for token in ("pool", "connection")):
        return CandidateCause(
            pattern_id=f"connection_pool_exhaustion_{service}",
            title=f"{service} connection pressure ({metric_name})",
            cause_service=service,
            affected_service=service,
            pattern_match_score=0.9,
            required_keywords=["pool", "connection", "exhaust", "timeout"],
            supporting_item_keys=[_safe_item_key(event)],
        )
    latency_tokens = ("latency", "duration", "response_time", "resolution_ms")
    if any(token in metric_lower for token in latency_tokens):
        return CandidateCause(
            pattern_id=f"latency_regression_{service}",
            title=f"{metric_name} critical latency in {service}",
            cause_service=service,
            affected_service=service,
            pattern_match_score=0.82,
            required_keywords=["latency", "timeout", "slow", "duration"],
            supporting_item_keys=[_safe_item_key(event)],
        )
    if "cpu" in metric_lower:
        return CandidateCause(
            pattern_id=f"cpu_saturation_{service}",
            title=f"{service} CPU saturation ({metric_name})",
            cause_service=service,
            affected_service=service,
            pattern_match_score=0.8,
            required_keywords=["cpu", "throttle", "saturation"],
            supporting_item_keys=[_safe_item_key(event)],
        )
    if any(token in metric_lower for token in ("memory", "heap", "oom")):
        return CandidateCause(
            pattern_id=f"memory_pressure_{service}",
            title=f"{service} memory pressure ({metric_name})",
            cause_service=service,
            affected_service=service,
            pattern_match_score=0.8,
            required_keywords=["memory", "heap", "oom"],
            supporting_item_keys=[_safe_item_key(event)],
        )
    return CandidateCause(
        pattern_id=f"metric_anomaly_{metric_name or 'unknown'}_{service}",
        title=f"{service} {metric_name or 'metric'} anomaly ({observed or 'unknown'})",
        cause_service=service,
        affected_service=service,
        pattern_match_score=0.62,
        required_keywords=[token for token in metric_lower.replace("-", "_").split("_") if token],
        supporting_item_keys=[_safe_item_key(event)],
    )


def _log_candidate(
    event: TimedEvent,
    default_service: str,
) -> CandidateCause:
    payload = event.payload
    service = _safe_service(event, default_service)
    signature = payload.get("signature", "")
    signature_lower = _normalized_text(signature)

    if "poolexhaust" in signature_lower or "connectionpool" in signature_lower:
        return CandidateCause(
            pattern_id=f"connection_pool_exhaustion_{service}",
            title=f"{service} connection pool exhausted ({signature})",
            cause_service=service,
            affected_service=service,
            pattern_match_score=0.93,
            required_keywords=["pool", "connection", "exhaust"],
            supporting_item_keys=[_safe_item_key(event)],
        )
    if "dns" in signature_lower or "nameresolution" in signature_lower:
        return CandidateCause(
            pattern_id=f"dns_failure_{service}",
            title=f"{service} DNS failure ({signature})",
            cause_service=service,
            affected_service=service,
            pattern_match_score=0.9,
            required_keywords=["dns", "timeout", "resolution"],
            supporting_item_keys=[_safe_item_key(event)],
        )
    if "timeout" in signature_lower or "deadlineexceeded" in signature_lower:
        return CandidateCause(
            pattern_id=f"timeout_cascade_{service}",
            title=f"{service} timeout cascade ({signature})",
            cause_service=service,
            affected_service=service,
            pattern_match_score=0.84,
            required_keywords=["timeout", "deadline", "slow"],
            supporting_item_keys=[_safe_item_key(event)],
        )
    if "oom" in signature_lower or "outofmemory" in signature_lower:
        return CandidateCause(
            pattern_id=f"memory_exhaustion_{service}",
            title=f"{service} memory exhaustion ({signature})",
            cause_service=service,
            affected_service=service,
            pattern_match_score=0.9,
            required_keywords=["memory", "oom", "heap"],
            supporting_item_keys=[_safe_item_key(event)],
        )
    return CandidateCause(
        pattern_id=f"error_pattern_{signature or 'unknown'}_{service}",
        title=f"{service} {signature or 'error signature'}",
        cause_service=service,
        affected_service=service,
        pattern_match_score=0.72,
        required_keywords=[
            token for token in signature_lower.replace("-", "_").split("_") if token
        ],
        supporting_item_keys=[_safe_item_key(event)],
    )


def _deployment_candidate(
    event: TimedEvent,
    default_service: str,
) -> CandidateCause:
    payload = event.payload
    service = _safe_service(event, default_service)
    version = payload.get("version", "")
    deployment_id = payload.get("deployment_id", "deployment")
    label = version or deployment_id
    return CandidateCause(
        pattern_id=f"deployment_regression_{service}",
        title=f"{service} regression after deployment {label}",
        cause_service=service,
        affected_service=service,
        pattern_match_score=0.78,
        required_keywords=["deploy", "regression", "change", "release"],
        supporting_item_keys=[_safe_item_key(event)],
    )


def build_candidate_causes(
    *,
    service: str,
    events: list[TimedEvent],
    topology_graph: dict[str, ServiceNode],
    pattern_hints: list[dict],
) -> list[CandidateCause]:
    candidates: list[CandidateCause] = []
    seen: dict[tuple[str, str, str], CandidateCause] = {}

    def add_candidate(candidate: CandidateCause) -> None:
        key = (candidate.pattern_id, candidate.cause_service, candidate.affected_service)
        existing = seen.get(key)
        if existing is not None:
            merged = list(
                dict.fromkeys(
                    existing.supporting_item_keys + candidate.supporting_item_keys
                )
            )
            existing.supporting_item_keys = merged
            existing.pattern_match_score = max(
                existing.pattern_match_score,
                candidate.pattern_match_score,
            )
            existing.required_keywords = list(
                dict.fromkeys(existing.required_keywords + candidate.required_keywords)
            )
            return
        seen[key] = candidate
        candidates.append(candidate)

    for event in events:
        if event.item_type == "metric_anomaly":
            add_candidate(_metric_candidate(event, service))
        elif event.item_type == "error_signature":
            add_candidate(_log_candidate(event, service))
        elif event.item_type == "deployment_change":
            add_candidate(_deployment_candidate(event, service))

    for pattern in pattern_hints:
        pattern_id = pattern.get("pattern_id", pattern.get("title", "unknown-pattern"))
        title = pattern.get("title", "Unknown pattern")
        cause_service = pattern.get("cause_service") or service
        affected_service = pattern.get("effect_service") or service
        if topology_graph and (
            not service_exists(cause_service, topology_graph)
            or not service_exists(affected_service, topology_graph)
        ):
            continue
        supporting_keys = [
            event.item_key
            for event in events
            if any(
                symptom.lower() in event.summary.lower() for symptom in pattern.get("symptoms", [])
            )
        ]
        add_candidate(
            CandidateCause(
                pattern_id=pattern_id,
                title=title,
                cause_service=cause_service,
                affected_service=affected_service,
                pattern_match_score=float(pattern.get("match_score", 0.0)),
                required_keywords=[symptom.lower() for symptom in pattern.get("symptoms", [])],
                supporting_item_keys=supporting_keys,
            )
        )

    base_services = {
        candidate.cause_service for candidate in candidates if candidate.pattern_match_score >= 0.6
    }
    for cause_service in sorted(base_services):
        upstream, downstream = _topology_neighbors(cause_service, topology_graph)
        for dependency in upstream:
            add_candidate(
                CandidateCause(
                    pattern_id=f"upstream_cascade_{dependency}_to_{cause_service}",
                    title=f"{cause_service} affected by upstream {dependency} degradation",
                    cause_service=dependency,
                    affected_service=cause_service,
                    pattern_match_score=0.5,
                    required_keywords=["dependency", "cascade", dependency.lower()],
                    supporting_item_keys=[],
                )
            )
        for dependent in downstream:
            add_candidate(
                CandidateCause(
                    pattern_id=f"downstream_pressure_{cause_service}_to_{dependent}",
                    title=f"{cause_service} pressure propagating to {dependent}",
                    cause_service=cause_service,
                    affected_service=dependent,
                    pattern_match_score=0.45,
                    required_keywords=["propagation", "downstream", dependent.lower()],
                    supporting_item_keys=[],
                )
            )

    if not candidates:
        candidates.append(
            CandidateCause(
                pattern_id="unknown_service_degradation",
                title="Unknown service degradation",
                cause_service=service,
                affected_service=service,
                pattern_match_score=0.2,
                required_keywords=[],
                supporting_item_keys=[event.item_key for event in events[:2]],
            )
        )
    candidates.sort(key=lambda candidate: candidate.pattern_match_score, reverse=True)
    return candidates
