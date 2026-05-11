#!/usr/bin/env sh

set -eu

API_BASE="${API_BASE:-http://localhost:8000}"

cat <<EOF
SentinelOps AI demo checklist
1. Ensure the Docker stack is running: docker compose up -d --build
2. Open the dashboard: http://localhost:3001
3. Trigger a sample webhook:

curl -X POST "${API_BASE}/incidents/webhook" \\
  -H "Content-Type: application/json" \\
  -H "Authorization: Bearer <demo-token>" \\
  -d '{
    "title": "Payment API latency exceeded threshold",
    "summary": "Latency crossed p99 threshold after deployment.",
    "severity": "high",
    "source": "prometheus",
    "labels": {"service": "payment-api"}
  }'

4. Start the workflow:
   POST ${API_BASE}/graph/incidents/{incident_id}/start
5. Watch trace updates:
   GET  ${API_BASE}/graph/incidents/{incident_id}/trace
   WS   ${API_BASE/https/ws}/ws/incidents/{incident_id}/stream
6. Review and action approvals:
   GET  ${API_BASE}/approvals
   POST ${API_BASE}/approvals/{incident_id}
7. Inspect postmortems and evaluations:
   GET ${API_BASE}/incidents/{incident_id}/postmortems
   GET ${API_BASE}/evaluations/summary
EOF
