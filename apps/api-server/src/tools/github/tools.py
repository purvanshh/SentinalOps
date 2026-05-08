from tools.github.client import GitHubClient
from tools.registry import ToolRegistry


def build_github_registry(client: GitHubClient | None = None) -> tuple[ToolRegistry, GitHubClient]:
    registry = ToolRegistry()
    github_client = client or GitHubClient()

    @registry.tool(
        name="get_recent_deployments",
        description="List recent deployments for a service.",
        parameters={
            "type": "object",
            "properties": {
                "service": {"type": "string"},
                "hours": {"type": "integer"},
            },
            "required": ["service"],
        },
    )
    async def recent_deployments(service: str, hours: int = 24) -> list[dict]:
        return await github_client.get_recent_deployments(service, hours)

    @registry.tool(
        name="get_commit_diff",
        description="Fetch a commit record for a commit SHA.",
        parameters={
            "type": "object",
            "properties": {
                "repo": {"type": "string"},
                "commit_sha": {"type": "string"},
            },
            "required": ["repo", "commit_sha"],
        },
    )
    async def commit_diff(repo: str, commit_sha: str) -> dict:
        return await github_client.get_commit_diff(repo, commit_sha)

    @registry.tool(
        name="get_rollback_candidates",
        description="List recent rollback candidates for a service.",
        parameters={
            "type": "object",
            "properties": {"service": {"type": "string"}},
            "required": ["service"],
        },
    )
    async def rollback_candidates(service: str) -> list[dict]:
        return await github_client.get_rollback_candidates(service)

    return registry, github_client
