# Payment API Latency Runbook

## Symptoms
- p99 latency climbs above 900ms
- connection pool saturation reaches 100%
- gateway starts returning 504s

## Investigation
1. Check recent deployments for payment-api.
2. Confirm whether connection pool or database latency changed first.
3. Compare current pod CPU with baseline.

## Safe Mitigation Options
- Roll back the latest deployment if correlation is strong.
- Scale stateless payment-api replicas if saturation is compute-bound.
- Avoid restarting the database without explicit approval.
