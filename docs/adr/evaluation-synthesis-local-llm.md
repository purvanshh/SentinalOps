# ADR: Evaluation Synthesis Uses Pinned Local LLM

## Context

The root-cause pipeline includes a constrained synthesis step that elevates
symptom-level evidence into cause-level hypothesis text. In production, this
step may use the primary LLM provider. In evaluation, a deterministic keyword
mock under-measures semantic capability.

## Decision

Evaluation synthesis should prefer a pinned local OpenAI-compatible model
configured through:

- `eval_synthesis_base_url`
- `eval_synthesis_api_key`
- `eval_synthesis_model`
- `eval_synthesis_temperature`
- `eval_synthesis_max_tokens`

The evaluation client forces deterministic parameters (`temperature=0.0`) and
caches identical prompts. If the local endpoint is unavailable, evaluation
falls back to the deterministic synthesis mock so the benchmark remains
reproducible instead of failing outright.

## Rationale

- A deterministic mock cannot perform nuanced symptom-to-cause inference.
- A pinned local model preserves the "mocked infrastructure" contract while
  enabling real semantic capability in the final translation layer.
- Prompt content contains no benchmark IDs, no golden labels, and no
  incident-specific tuning.

## Determinism Guarantees

- `temperature=0.0`
- pinned model name
- identical prompts cached in-process
- benchmark can be verified with repeated runs

## Current Limitation

If the local model endpoint is unavailable, evaluation automatically uses the
deterministic fallback synthesizer. In that situation, evaluation remains
stable but continues to under-measure production semantic capability.
