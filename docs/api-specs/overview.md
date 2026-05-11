# API Surface Overview

Core routes currently exposed:

- `POST /incidents/webhook`
- `GET /incidents`
- `GET /incidents/{id}`
- `GET /incidents/{id}/postmortems`
- `GET /approvals`
- `POST /approvals/{incident_id}`
- `POST /graph/incidents/{incident_id}/start`
- `POST /graph/incidents/{incident_id}/resume`
- `GET /graph/incidents/{incident_id}/state`
- `GET /graph/incidents/{incident_id}/graph-state`
- `GET /graph/incidents/{incident_id}/trace`
- `WS /ws/incidents/{incident_id}/stream`
- `GET /evaluations/summary`
- `GET /health`
- `GET /metrics`

## OpenAPI export

The FastAPI app serves interactive documentation at `/docs` and a machine-readable schema at `/openapi.json` when the stack is running.
