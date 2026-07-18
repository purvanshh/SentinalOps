# Root Cause Analysis (RCA) Accuracy Decomposition

## 1. Problem Statement
The current root-cause accuracy in SentinelOps is 8.2%. The system produces plausible but generic hypotheses, and there is no learned causal inference or robust matching. To improve this, we must decompose the problem into sub-problems and classify failures using a structured taxonomy.

## 2. RCA Failure Taxonomy
We categorize misdiagnoses into five failure modes:
1. **missing_evidence**: The telemetry collected was insufficient or crucial logs/metrics were missing.
2. **wrong_evidence_weight**: Evidence was collected, but the reasoning engine gave too much weight to irrelevant symptoms or too little to critical signals (e.g., OOM kill logs).
3. **temporal_confusion**: Causal paths were inferred in the wrong temporal direction (e.g., assuming a database latency spike caused a CPU surge, when the CPU surge actually occurred first).
4. **generic_fallback**: The system defaulted to a generic hypothesis (e.g., "unknown service degradation") because of LLM errors, schema validation failures, or weak retrieval matching.
5. **pattern_mismatch**: Historical or expert runbooks were retrieved but incorrectly matched due to low semantic similarity score or bad hybrid search retrieval.

## 3. Per-Category Accuracy Analysis Methodology
Each incident in the benchmark suite belongs to a specific category. We measure accuracy per category by:
* Mapping the output of `RootCauseAnalysis` to the benchmark incident's `golden_root_cause`.
* Classifying any failure (where the lexical/semantic similarity score is below 0.6) using the taxonomy described above.
* Aggregating counts to find the weakest areas of the system.

## 4. Constrained Experiment Design
To achieve the target accuracy of >80% on a subset, we limit our focus to three incident categories:
1. **database_failure**: Spikes in DB connection pools, transaction locks, and slow queries.
2. **memory_pressure**: Container OOM kills, memory leaks, and GC pauses.
3. **deployment_regression**: Failures correlating with recent code changes or container redeployments.

## 5. Proposed Algorithmic Changes
* **Evidence Weighting**: Prioritize metrics (OOM, database locks) over raw logs.
* **Heuristic Rules**: Implement high-precision rules for the three target categories.
* **Calibration**: Recalibrate LLM confidence output to reflect actual system accuracy.
