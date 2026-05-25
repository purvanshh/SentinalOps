#!/bin/bash
set -e

echo "=== Triple-Run Evaluation with pinned eval synthesis model ==="
echo "Run 1 starting..."
PYTHONPATH=apps/api-server/src ./.venv/bin/python - <<'PY' 2>&1 | tee /tmp/eval_log_1.txt
from evaluation.runner import run_evaluation
import asyncio, json
r = asyncio.run(run_evaluation())
json.dump(r, open('/tmp/eval_run_1.json', 'w'), indent=2, default=str)
print('Run 1 complete')
PY

echo "Run 2 starting..."
PYTHONPATH=apps/api-server/src ./.venv/bin/python - <<'PY' 2>&1 | tee /tmp/eval_log_2.txt
from evaluation.runner import run_evaluation
import asyncio, json
r = asyncio.run(run_evaluation())
json.dump(r, open('/tmp/eval_run_2.json', 'w'), indent=2, default=str)
print('Run 2 complete')
PY

echo "Run 3 starting..."
PYTHONPATH=apps/api-server/src ./.venv/bin/python - <<'PY' 2>&1 | tee /tmp/eval_log_3.txt
from evaluation.runner import run_evaluation
import asyncio, json
r = asyncio.run(run_evaluation())
json.dump(r, open('/tmp/eval_run_3.json', 'w'), indent=2, default=str)
print('Run 3 complete')
PY

echo ""
echo "=== Comparison ==="
./.venv/bin/python - <<'PY'
import json
runs = [json.load(open(f'/tmp/eval_run_{i}.json')) for i in [1, 2, 3]]
keys = [
    'root_cause_accuracy_lexical',
    'root_cause_accuracy_semantic',
    'mean_semantic_similarity',
    'safety_score',
    'grounding_score',
]
for k in keys:
    vals = [r[k] for r in runs]
    match = len(set(f'{v:.6f}' for v in vals)) == 1
    print(f'{k}:')
    for i, v in enumerate(vals, 1):
        print(f'  Run {i}: {v}')
    print(f'  Deterministic: {"YES" if match else "NO — INVESTIGATE"}')
    print()
PY
