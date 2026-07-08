from __future__ import annotations

from datetime import datetime
from typing import Any

import structlog
from agents.prompts.rca_prompts import EVIDENCE_SYNTHESIS_TEMPLATE
from agents.rca_structured import EvidenceItem, SynthesizedNarrative
from core.resilience.resilient_llm_client import ResilientLLMClient
from jinja2 import Template

logger = structlog.get_logger(__name__)


def map_to_evidence_items(simplified_evidence: list[dict[str, Any]]) -> list[EvidenceItem]:
    """Map raw normalized evidence dicts into structured EvidenceItem models."""
    items = []
    for item in simplified_evidence:
        source_str = str(item.get("source", "")).lower()
        if "metric" in source_str:
            source = "metrics"
        elif "log" in source_str:
            source = "logs"
        elif "deploy" in source_str:
            source = "deployment"
        else:
            item_type = str(item.get("item_type", "")).lower()
            if "metric" in item_type:
                source = "metrics"
            elif "log" in item_type or "error" in item_type:
                source = "logs"
            elif "deploy" in item_type:
                source = "deployment"
            else:
                source = "metrics"

        ts_str = item.get("timestamp") or item.get("time") or item.get("retrieval_timestamp")
        if not ts_str:
            ts = datetime.utcnow()
        else:
            try:
                if isinstance(ts_str, str):
                    ts_str_clean = ts_str.replace("Z", "+00:00")
                    ts = datetime.fromisoformat(ts_str_clean)
                else:
                    ts = ts_str
            except Exception:
                ts = datetime.utcnow()

        service = item.get("service") or "unknown-service"

        item_type = item.get("item_type", "")
        if item_type == "metric_anomaly":
            signal = item.get("metric") or "metric_anomaly"
            value = (
                f"observed={item.get('observed')}, expected={item.get('expected_range')}, "
                f"z={item.get('z_score')}"
            )
        elif item_type == "error_signature":
            signal = item.get("signature") or "log_error"
            value = f"count={item.get('count')}, first_seen={item.get('first_seen')}"
        elif item_type == "deployment_change":
            signal = f"deployment_{item.get('version') or item.get('deployment_id')}"
            value = f"commit_sha={item.get('commit_sha')}, files={item.get('files_changed')}"
        else:
            signal = item.get("signal") or "unknown_signal"
            value = item.get("value")

        severity = "unknown"
        sev_val = item.get("severity")
        if sev_val in ["info", "warning", "critical", "unknown"]:
            severity = sev_val
        elif item.get("z_score"):
            try:
                if abs(float(item.get("z_score"))) > 5:
                    severity = "critical"
            except (ValueError, TypeError):
                pass
        elif item.get("count"):
            try:
                if int(item.get("count")) > 10:
                    severity = "critical"
            except (ValueError, TypeError):
                pass

        items.append(
            EvidenceItem(
                evidence_id=item.get("item_key") or f"EVID-{len(items)+1}",
                source=source,
                timestamp=ts,
                service=service,
                signal=signal,
                value=value,
                severity=severity,
                confidence=float(item.get("confidence", 1.0)),
            )
        )
    return items


class EvidenceSynthesisAgent:
    """Agent that synthesizes parallel evidence streams into a single timeline narrative."""

    def __init__(self, llm_client: Any | None = None) -> None:
        self.llm = llm_client or ResilientLLMClient()

    async def synthesize(
        self,
        incident_id: str,
        simplified_evidence: list[dict[str, Any]],
        primary_service: str = "unknown-service",
    ) -> SynthesizedNarrative:
        evidence_items = map_to_evidence_items(simplified_evidence)
        evidence_by_source = {
            "metrics": [e for e in evidence_items if e.source == "metrics"],
            "logs": [e for e in evidence_items if e.source == "logs"],
            "deployment": [e for e in evidence_items if e.source == "deployment"],
        }

        # Render prompt using Jinja2
        prompt = Template(EVIDENCE_SYNTHESIS_TEMPLATE).render(evidence_by_source=evidence_by_source)

        messages = [
            {
                "role": "system",
                "content": (
                    "You are an evidence synthesis engine. Return only a valid JSON "
                    "object matching the SynthesizedNarrative schema."
                ),
            },
            {"role": "user", "content": prompt},
        ]

        logger.info(
            "synthesis_agent_calling_llm",
            incident_id=incident_id,
            metrics_count=len(evidence_by_source["metrics"]),
            logs_count=len(evidence_by_source["logs"]),
            deployment_count=len(evidence_by_source["deployment"]),
        )

        try:
            res = await self.llm.generate(
                messages,
                structured_output_model=SynthesizedNarrative,
                temperature=0.0,
            )
            # Handle ResilientLLMClient returning (response, chain_result)
            if isinstance(res, tuple):
                response = res[0]
            else:
                response = res

            if isinstance(response, SynthesizedNarrative):
                return response

            # Fallback if dictionary returned
            if isinstance(response, dict):
                return SynthesizedNarrative.model_validate(response)

        except Exception as exc:
            logger.error("synthesis_agent_failed_falling_back", error=str(exc))

        # Hard fallback: construct a basic SynthesizedNarrative from inputs
        return self.build_fallback_narrative(incident_id, evidence_items, primary_service)

    def build_fallback_narrative(
        self,
        incident_id: str,
        evidence_items: list[EvidenceItem],
        primary_service: str,
    ) -> SynthesizedNarrative:
        summary = (
            "Evidence synthesis failed or fallback triggered. "
            "Using raw correlated event fragments."
        )
        if evidence_items:
            summary += f" Detected {len(evidence_items)} telemetry anomalies across the system."

        anomalies = [f"{e.service}:{e.signal}" for e in evidence_items if e.severity == "critical"]
        if not anomalies and evidence_items:
            anomalies = [f"{e.service}:{e.signal}" for e in evidence_items]

        return SynthesizedNarrative(
            narrative_id=f"narrative-{incident_id}-{datetime.utcnow().strftime('%s')}",
            incident_id=incident_id,
            summary=summary,
            timeline=evidence_items,
            correlations=[],
            anomalies=anomalies,
            missing_telemetry=[],
            primary_affected_service=primary_service,
            confidence_per_source={"metrics": 0.5, "logs": 0.5, "deployment": 0.5},
        )
