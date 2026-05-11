# Demo Script

## Setup

1. Start the stack with `docker compose up -d --build`.
2. Open the dashboard at `http://localhost:3001`.
3. Keep the API docs open at `http://localhost:8000/docs`.

## Walkthrough

1. Show the incident board and evaluation summary on the landing page.
2. Trigger a sample payment latency incident through `POST /incidents/webhook`.
3. Start the workflow graph and explain the evidence fan-out across metrics, logs, and deployment.
4. Open the graph trace endpoint and the WebSocket stream to show live state progression.
5. Pause at the approval queue and explain the safety gate.
6. Approve the remediation path and show the execution/postmortem flow.
7. End with `GET /evaluations/summary` and the PRD checklist in [docs/prd-compliance-checklist.md](/Users/purvansh/Desktop/Projects/SentinalOps/docs/prd-compliance-checklist.md:1).
