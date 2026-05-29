# Runtime Diagnostics Report

**Date:** 2026-05-16
**Components:** ConfidenceDriftMonitor, ReasoningCollapseDetector, RuntimeIntegritySnapshot, TelemetryHealthMonitor

---

## Overview

The Phase 50 diagnostics layer provides live runtime introspection across
four health dimensions. All diagnostics expose three output formats:
- **Prometheus metrics** (for Grafana/alerting integration)
- **JSON diagnostics** (for structured log pipelines)
- **Operator-readable summaries** (for on-call engineers)

---

## Confidence Drift Monitor

Monitors a sliding window of confidence scores for four alert conditions:

| Alert Type | Condition | Severity |
|---|---|---|
| `confidence_inflation` | mean >0.85 AND std <0.05 | warning |
| `confidence_collapse` | mean <0.20 | critical |
| `confidence_instability` | std >0.30 | warning |
| `confidence_floor_violation` | mean <0.05 | critical |

**Default window size:** 50 observations

**Prometheus metrics exposed:**
- `sentinelops_confidence_mean`
- `sentinelops_confidence_std`
- `sentinelops_confidence_min` / `max`
- `sentinelops_confidence_observations`
- `sentinelops_confidence_alerts_total`

---

## Reasoning Collapse Detector

Detects structural output failures on a per-incident basis:

| Collapse Type | Condition | Severity |
|---|---|---|
| `confidence_without_evidence` | confidence >0.70 AND no attribution | high |
| `empty_explanation` | explanation <10 chars AND confidence >0.50 | medium |
| `contradictory_severity` | severity=low AND error_rate >0.80 | high |
| `circular_reasoning` | symptom == attribution (exact match) | medium |

**Prometheus metrics exposed:**
- `sentinelops_reasoning_collapse_total`
- `sentinelops_reasoning_collapse_by_type{type="..."}`

---

## Runtime Integrity Snapshot

Point-in-time composite scoring of system health.

**Integrity score formula:**
```
1.0
- 0.20 if mean_confidence < 0.20 or > 0.90
- min(0.40, collapse_rate × 0.10)
- min(0.30, active_alerts × 0.10)
```

**System state classification:**
- `nominal`: integrity ≥ 0.70, no critical alerts
- `degraded`: integrity < 0.70
- `critical`: integrity < 0.40 OR any critical-severity alert

**Prometheus metrics exposed:**
- `sentinelops_integrity_score`
- `sentinelops_system_state{state="..."}`
- `sentinelops_active_alerts`

---

## Telemetry Health Monitor

Tracks incoming telemetry quality across a sliding window.

**Impossible value checks:**
- `error_rate < 0 or > 1`
- `success_rate < 0 or > 1`
- `latency_p99 < 0`
- `requests_per_second < 0`

**Required fields:** `error_rate`, `latency_p99`

**Health score formula:**
```
1.0
- (corrupt_rate × 0.50)
- (missing_field_rate × 0.25)
- (impossible_value_rate × 0.25)
```

**Status thresholds:** healthy ≥ 0.80, degraded ≥ 0.50, corrupt < 0.50

**Prometheus metrics exposed:**
- `sentinelops_telemetry_health_score`
- `sentinelops_telemetry_corrupt_samples_total`
- `sentinelops_telemetry_missing_field_rate`
- `sentinelops_telemetry_staleness_seconds`

---

## Limitations

- The diagnostics are passive observers — they report health, they do not remediate.
- All monitors operate on the application process's in-memory state.
  There is no persistent diagnostics store across restarts.
- Alert thresholds are statically configured. Adaptive thresholds
  based on baseline variance are not implemented.
