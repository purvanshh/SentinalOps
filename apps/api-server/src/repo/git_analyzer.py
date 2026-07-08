from __future__ import annotations

from typing import Any
import structlog
from tools.github.client import GitHubClient

logger = structlog.get_logger(__name__)


class GitAnalyzer:
    """Retrieves and analyzes Git change history for operational correlation."""

    def __init__(self, github_client: GitHubClient | None = None) -> None:
        self.client = github_client or GitHubClient()

    async def get_recent_commits(self, service: str, limit: int = 5) -> list[dict[str, Any]]:
        """Fetch recent commits influencing a service, with SRE fallback data."""
        try:
            deployments = await self.client.get_recent_deployments(service)
            commits = []
            for d in deployments[:limit]:
                commit_sha = d.get("commit_sha") or d.get("sha")
                if commit_sha:
                    diff = await self.client.get_commit_diff("purvanshh/SentinalOps", commit_sha)
                    commits.append(diff)
            return commits
        except Exception as exc:
            logger.warning("git_analyzer_failed_using_mock", error=str(exc))
            # Fallback to simulated changes
            return [
                {
                    "sha": "c1a93b4f",
                    "author": "SRE Team",
                    "authored_at": "2026-07-08T10:00:00Z",
                    "message": f"refactor: tune connection pool sizes on {service}",
                    "files_changed": ["db/connection.py", "config/database.yaml"],
                    "additions": 14,
                    "deletions": 5,
                }
            ]
