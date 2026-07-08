from __future__ import annotations

import re
from typing import Any


class ReleaseParser:
    """Parses deployment version tags and release message history to extract git metadata."""

    def parse_release(self, version_tag: str, release_notes: str) -> dict[str, Any]:
        # Match standard commit hashes in versions like v1.0.0-c1a93b4f
        sha_match = re.search(r"-[a-f0-9]{7,8}", version_tag)
        sha = sha_match.group(0).lstrip("-") if sha_match else "unknown"

        change_type = "minor"
        lower_notes = release_notes.lower()
        if "refactor" in lower_notes or "perf" in lower_notes or "pool" in lower_notes:
            change_type = "config_drift"
        elif "feature" in lower_notes or "feat" in lower_notes:
            change_type = "feature_release"
        elif "fix" in lower_notes or "bug" in lower_notes:
            change_type = "bug_fix"

        return {
            "version": version_tag,
            "commit_sha": sha,
            "change_type": change_type,
            "description": release_notes,
        }
