from typing import Any

import httpx
from core.config import get_settings


class GitHubClient:
    def __init__(
        self,
        base_url: str | None = None,
        token: str | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        settings = get_settings()
        self.base_url = (base_url or settings.github_api_url).rstrip("/")
        self.token = token or settings.github_token
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=15.0,
            transport=transport,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/vnd.github+json",
            },
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def get_recent_deployments(self, service: str, hours: int = 24) -> list[dict[str, Any]]:
        response = await self._client.get(
            "/deployments", params={"service": service, "hours": hours}
        )
        response.raise_for_status()
        payload = response.json()
        if isinstance(payload, dict):
            return payload.get("deployments", [])
        return payload

    async def get_commit_diff(self, repo: str, commit_sha: str) -> dict[str, Any]:
        response = await self._client.get(f"/repos/{repo}/commits/{commit_sha}")
        response.raise_for_status()
        raw = response.json()
        return _extract_commit_metadata(raw)


def _extract_commit_metadata(raw: dict[str, Any]) -> dict[str, Any]:
    """Extract structured provenance fields from a GitHub commits API response."""
    commit_block = raw.get("commit", {})
    author_block = commit_block.get("author", {}) or {}
    files = raw.get("files", []) or []
    return {
        "sha": raw.get("sha", ""),
        "author": author_block.get("name", ""),
        "authored_at": author_block.get("date", ""),
        "message": commit_block.get("message", ""),
        "files_changed": [f["filename"] for f in files if "filename" in f],
        "additions": sum(f.get("additions", 0) for f in files),
        "deletions": sum(f.get("deletions", 0) for f in files),
        "url": raw.get("html_url", ""),
    }

    async def get_rollback_candidates(self, service: str) -> list[dict[str, Any]]:
        response = await self._client.get(f"/deployments/{service}/rollback-candidates")
        response.raise_for_status()
        payload = response.json()
        if isinstance(payload, dict):
            return payload.get("deployments", [])
        return payload
