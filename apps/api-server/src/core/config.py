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
    prometheus_url: str = Field(default="http://localhost:9090")
    grafana_url: str = Field(default="http://localhost:3000")
    loki_url: str = Field(default="http://localhost:3100")
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


@lru_cache
def get_settings() -> Settings:
    return Settings()
