# INCIDENT EVALUATION SUITE — Phase 39

## Summary

| Attribute | Value |
|-----------|-------|
| Suite ID | `benchmark-v1` |
| Schema Version | 1.0 |
| Created | 2026-05-13 |
| Total Incidents | **106** |
| Categories | 14 |
| Status | **VERIFIED** |

## Purpose

This benchmark suite provides a repeatable, labeled evaluation corpus for measuring
AI decision quality in SentinelOps. Every incident has human-verified ground truth
labels for classification, root cause, remediation correctness, operator action,
confidence range, and risk tier.

## Category Distribution

| Category | Count | Description |
|----------|-------|-------------|
| `latency_spike` | 12 | p99/p95 latency exceeding thresholds |
| `deployment_regression` | 12 | Post-deploy error rate / behavior change |
| `memory_leak` | 10 | Unbounded memory growth, OOM kills |
| `cpu_saturation` | 10 | CPU throttling, infinite loops, batch collision |
| `redis_outage` | 8 | Primary down, eviction storms, cluster split |
| `postgresql_failure` | 8 | Connection exhaustion, lock contention, disk full |
| `networking_failure` | 8 | Partitions, DNS failure, MTU mismatch, mTLS issues |
| `cascading_failure` | 8 | Multi-system failures, alert storms, DNS cascade |
| `noisy_alert` | 8 | Threshold sensitivity, flapping, false positives |
| `false_positive` | 6 | Authorized activity triggering real alerts |
| `disk_exhaustion` | 4 | Log rotation failure, core dumps, image cache |
| `dns_failure` | 4 | CoreDNS crash, ndots misconfiguration, stale cache |
| `intermittent_outage` | 4 | Race conditions, health flapping, external deps |
| `kubernetes_pod_failure` | 4 | CrashLoopBackOff, OOMKilled, image pull errors |

## Benchmark Incident Schema

Each incident contains:

```json
{
  "id": "BM-001",
  "name": "latency-spike-payment-p99-high",
  "version": "1.0",
  "category": "latency_spike",
  "description": "...",
  "alert_payload": { "title", "summary", "severity", "source", "labels", "annotations" },
  "metrics_snapshot": [{ "metric", "observed", "expected_range", "z_score" }],
  "logs_sample": [{ "signature", "count", "first_seen", "sample", "trace_ids" }],
  "mocked_tool_responses": { "router", "metrics", "logs", "deployment" },
  "golden_classification": "latency",
  "golden_severity": "high",
  "golden_root_cause": "...",
  "golden_remediation": "...",
  "golden_remediation_class": "SAFE_AND_CORRECT",
  "golden_expected_blast_radius_mean": 750,
  "golden_remediation_safe": true,
  "golden_operator_action": "APPROVE",
  "expected_confidence_range": [0.8, 0.95],
  "is_noisy_alert": false,
  "is_false_positive": false,
  "requires_escalation": false,
  "risk_tier": "MODERATE"
}
```

## Remediation Class Distribution

| Class | Count | Description |
|-------|-------|-------------|
| `SAFE_AND_CORRECT` | 69 (65%) | Correct diagnosis, safe and actionable steps |
| `PARTIALLY_CORRECT` | 14 (13%) | Incomplete or ambiguous but not harmful |
| `SAFE_BUT_USELESS` | 13 (12%) | False positives; correct to dismiss |
| `DANGEROUS` | 8 (8%) | Contains operations that could cause further damage |
| `HALLUCINATED` | 2 (2%) | References non-existent infrastructure |

## Risk Tier Distribution

| Tier | Count |
|------|-------|
| LOW | 32 (30%) |
| MODERATE | 48 (45%) |
| HIGH | 18 (17%) |
| CRITICAL | 8 (8%) |

## Special Incident Coverage

| Characteristic | Count |
|----------------|-------|
| False positives (`is_false_positive=true`) | 16 |
| Noisy alerts (`is_noisy_alert=true`) | 16 |
| Requires escalation | 26 |
| Low-confidence incidents (max confidence < 0.65) | 15 |
| DANGEROUS remediations | 8 |
| HALLUCINATED remediations | 2 |

## Validation Results

| Check | Status |
|-------|--------|
| No duplicate IDs | VERIFIED |
| All incidents have golden labels | VERIFIED |
| All remediation classes valid | VERIFIED |
| All risk tiers valid | VERIFIED |
| All confidence ranges valid | VERIFIED |
| All operator actions valid | VERIFIED |
| Deterministic load (two loads produce identical order) | VERIFIED |
| All 14 required categories present | VERIFIED |
| Each category has >= 4 incidents | VERIFIED |
| Suite passes `validate_suite()` with zero errors | VERIFIED |

## Benchmark Reproducibility

The benchmark fixture is stored as a static JSON file at:

```
simulation/datasets/evaluation/benchmark_suite_v1.json
```

Replay hash (stable across runs): `ddf715d1d54bba67`

Loading is deterministic: the same incident order and labels are produced
on every load, ensuring evaluation reproducibility across environments.

## Future Suite Versions

| Version | Changes |
|---------|---------|
| v1.0 | 106 incidents, 14 categories (current) |
| v2.0 (planned) | Add provider-degraded incidents; add alert-storm scenarios |
| v3.0 (planned) | Add multi-tenant incidents; add SLO breach scenarios |

Version bumps require new `benchmark_suite_v2.json` and regression comparison
against v1.0 baseline scores before accepting.
