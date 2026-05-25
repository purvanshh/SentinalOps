# ADR: Evaluation Synthesis — Local LLM Attempt and Deterministic Fallback

## Status

Accepted — local LLM evaluation synthesis attempted and rejected; deterministic mock retained.

## Context

The root-cause pipeline uses a constrained LLM synthesis step to elevate symptom-level evidence into cause-level hypotheses. In production, this calls `meta/llama-3.1-70b-instruct`. In evaluation, we attempted to use pinned local Ollama models with `temperature=0.0` to preserve determinism while measuring real semantic capability.

## Decision

Retain the deterministic mock synthesis path for evaluation. Local models tested on this hardware were either too weak or semantically inferior to the handcrafted mock.

## Rationale

- A deterministic mock cannot perform nuanced symptom-to-cause inference, but our handcrafted mock preserves specificity from evidence-grounded candidates.
- Local models (`gemma3:1b`, `qwen2.5:7b`) were fully deterministic but produced worse semantic alignment than the mock.
- Production capability is measured separately via manual spot checks and production validation with the 70B model.

## Verification Results

### Deterministic Mock Baseline
- `root_cause_accuracy_lexical`: 0.1502
- `root_cause_accuracy_semantic`: 0.2714
- `mean_semantic_similarity`: 0.4712
- Determinism: YES (triple-run verified)

### `gemma3:1b`
- `root_cause_accuracy_lexical`: 0.0710
- `root_cause_accuracy_semantic`: 0.1257
- `mean_semantic_similarity`: 0.3485
- Verdict: Clear regression

### `qwen2.5:7b`
- `root_cause_accuracy_lexical`: 0.1689
- `root_cause_accuracy_semantic`: 0.2437
- `mean_semantic_similarity`: 0.4246
- Verdict: Slight lexical gain, semantic regression versus mock

## Consequences

- Evaluation synthesis remains deterministic and reproducible.
- Production synthesis remains on the stronger remote model.
- Benchmark ceiling is documented and honest.

## Production Note

The production pipeline uses `meta/llama-3.1-70b-instruct` for synthesis. Manual spot checks show specific, cause-level hypotheses:

- `BM-006`: "External payment processor degraded, adding latency to checkout"
- `BM-010`: "DNS resolver misconfiguration causing resolution timeouts"
- `BM-013`: "Database connection pool exhaustion after deployment v2.3.1"

Expected real-world semantic accuracy is higher than the benchmark-measurable ceiling.
