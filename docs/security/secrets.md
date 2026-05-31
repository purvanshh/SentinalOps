# Secrets Management and Rotation Policy

SentinelOps requires secure storage and lifecycle handling of all authentication secrets and provider keys.

## Rotation Process
1. Rotate LLM provider keys via cloud provider dashboards.
2. Update the environment variables in vault/production configuration.
3. Restart Celery worker processes to clear memory-cached values.
