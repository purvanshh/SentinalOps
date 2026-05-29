# Reproducibility Report

**Date:** 2026-05-16
**Framework:** Phase 50 ReplayManifest + DatasetFingerprint + EnvironmentValidator

---

## What Reproducibility Means Here

A benchmark run is reproducible if:
1. The same dataset produces the same fingerprint
2. The same seed produces the same evaluation scaffold outputs
3. The environment (Python version, package versions) is captured and versioned
4. The result checksums match when verified against the manifest

Reproducibility does **not** extend to LLM reasoning outputs, which are
inherently non-deterministic due to sampling.

---

## Fingerprinting Methodology

**Algorithm:** SHA-256 (truncated to 16 hex characters for readability)

**Dataset fingerprint inputs:**
- All incident records serialized to JSON with sorted keys
- Sorted lexicographically before hashing (order-independent)
- Includes label distribution and schema hash as separate components
- First 10 records contribute individual sample checksums

**Environment fingerprint inputs:**
- All installed Python package names and versions
- Python version string
- Platform identifier

---

## Replay Manifest Schema

Each manifest entry records:

```json
{
  "run_id": "string",
  "timestamp": "unix float",
  "benchmark_version": "string",
  "dataset_checksum": "16-char hex",
  "environment_hash": "16-char hex",
  "seed": "integer",
  "parameters": "dict",
  "result_checksum": "16-char hex",
  "passed": "boolean",
  "notes": "string"
}
```

The `result_checksum` is computed from the JSON-serialized result dict
(sorted keys). Verification compares the re-computed checksum to the stored value.

---

## Drift Detection Capabilities

| Drift Type | Detection Method |
|---|---|
| Dataset row mutation | Full dataset SHA-256 mismatch |
| Row count change | item_count field comparison |
| Schema change (new/removed fields) | schema_hash comparison |
| Label distribution shift | label_distribution field comparison |
| Package version change | Per-package version diff |
| Python version change | python_version string comparison |
| Hidden randomness | Dual-run output checksum comparison |
| Benchmark contamination | Score inflation >15% across ≥50% of metrics |

---

## Reproducibility Guarantees

**Guaranteed reproducible:**
- Dataset fingerprint (same records → same hash)
- Environment hash (same packages → same hash)
- Evaluation scaffold logic (seed-controlled random calls)
- Benchmark metric computation from given outputs

**Not guaranteed reproducible:**
- LLM reasoning text (non-deterministic even with fixed temperature)
- External API response times
- OS-level process scheduling effects on async timing

---

## Caveats

The reproducibility layer validates the evaluation framework, not the
AI reasoning system. A benchmark with identical infrastructure inputs
may produce different scores if the LLM API changes its underlying model
or sampling behavior without a version bump.

External auditors should run evaluations against frozen dataset snapshots
with pinned environment files (`uv.lock` is committed for this purpose).
