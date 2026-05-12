from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    project_name: str = Field(default="SentinelOps AI")
    app_env: str = Field(default="development")
    api_host: str = Field(default="0.0.0.0")
    api_port: int = Field(default=8000)
    api_reload: bool = Field(default=True)

    postgres_server: str = Field(default="localhost")
    postgres_port: int = Field(default=5432)
    postgres_db: str = Field(default="sentinelops")
    postgres_user: str = Field(default="sentinelops")
    postgres_password: str = Field(default="sentinelops")

    redis_url: str = Field(default="redis://localhost:6379/0")
    qdrant_url: str = Field(default="http://localhost:6333")
    qdrant_pattern_collection: str = Field(default="patterns")
    qdrant_incident_collection: str = Field(default="past_incidents")
    qdrant_runbook_collection: str = Field(default="runbooks")
    qdrant_prevention_collection: str = Field(default="prevention_items")
    prometheus_url: str = Field(default="http://localhost:9090")
    grafana_url: str = Field(default="http://localhost:3000")
    loki_url: str = Field(default="http://localhost:3100")
    tempo_url: str = Field(default="http://localhost:3200")
    topology_path: str = Field(default="configs/development/topology.yaml")
    github_api_url: str = Field(default="https://api.github.com")
    github_token: str = Field(default="dummy-token")
    slack_webhook_url: str = Field(default="")
    approval_timeout_minutes: int = Field(default=15)
    approval_auto_reject_minutes: int = Field(default=30)
    api_rate_limit_per_minute: int = Field(default=120)

    celery_broker_url: str = Field(default="redis://localhost:6379/1")
    celery_result_backend: str = Field(default="redis://localhost:6379/2")
    default_agent_timeout_seconds: int = Field(default=30)
    llm_base_url: str = Field(default="http://localhost:11434/v1")
    llm_api_key: str = Field(default="dummy-key")
    llm_model: str = Field(default="gpt-oss-120b")
    llm_secondary_base_url: str = Field(default="")
    llm_secondary_api_key: str = Field(default="")
    llm_secondary_model: str = Field(default="gpt-4.1-mini")
    llm_local_base_url: str = Field(default="http://localhost:11434/v1")
    llm_local_model: str = Field(default="llama3.2")
    auth0_domain: str = Field(default="sentinelops.local")
    auth0_audience: str = Field(default="sentinelops-api")
    auth0_algorithms: str = Field(default="HS256")
    auth0_issuer: str | None = Field(default=None)
    auth0_secret_key: str = Field(default="dev-secret-change-me")
    approval_token_secret: str = Field(default="approval-secret-change-me")
    tool_allowlist_path: str = Field(default="configs/production/tool_allowlist.yaml")
    backup_oncall_targets: str = Field(default="backup-oncall")

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_server}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def auth_issuer(self) -> str:
        return self.auth0_issuer or f"https://{self.auth0_domain}/"

    @property
    def backup_oncall_list(self) -> list[str]:
        return [item.strip() for item in self.backup_oncall_targets.split(",") if item.strip()]

    @property
    def is_production(self) -> bool:
        return self.app_env in ("production", "prod")

    def validate_production_secrets(self) -> list[str]:
        """Return a list of insecure-secret warnings.

        Returns an empty list in non-production environments.
        Call at startup: if the list is non-empty in production, raise.
        """
        if not self.is_production:
            return []
        issues: list[str] = []
        if self.auth0_secret_key == "dev-secret-change-me":
            issues.append("AUTH0_SECRET_KEY is using the default development value")
        if self.approval_token_secret == "approval-secret-change-me":
            issues.append("APPROVAL_TOKEN_SECRET is using the default development value")
        return issues

    def validate_required_configuration(self) -> list[str]:
        """Return a list of configuration warnings for any environment.

        These are not necessarily security issues but represent incomplete
        configurations that would cause runtime failures.
        """
        issues: list[str] = []
        if not self.postgres_server or self.postgres_server == "localhost" and self.is_production:
            issues.append("POSTGRES_SERVER is 'localhost' in a production environment")
        if not self.redis_url:
            issues.append("REDIS_URL is not configured")
        if not self.celery_broker_url:
            issues.append("CELERY_BROKER_URL is not configured")
        if self.llm_api_key == "dummy-key" and self.is_production:
            issues.append("LLM_API_KEY is using the dummy development value in production")
        return issues


@lru_cache
def get_settings() -> Settings:
    return Settings()
