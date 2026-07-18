"""
Organizational Knowledge Graph for SentinelOps Phase 12 (bundled with Phase 11).

Encodes organizational knowledge that human SREs know implicitly:
    - Teams → Services → Owners → Historical incidents → Failure frequencies
    - "Payments Team always breaks DNS after releases"

This knowledge graph augments investigation with organizational context.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class TeamProfile:
    """Profile of a team with their services, failure history, and patterns."""

    team_name: str
    services: List[str] = field(default_factory=list)
    owners: List[str] = field(default_factory=list)
    common_failure_modes: List[str] = field(default_factory=list)
    incident_count: int = 0
    mean_resolution_minutes: float = 0.0
    known_risks: List[str] = field(default_factory=list)


@dataclass
class ServiceProfile:
    """Organizational profile of a service with failure history."""

    service_name: str
    team: str
    dependencies: List[str] = field(default_factory=list)
    dependents: List[str] = field(default_factory=list)
    failure_frequency: float = 0.0  # incidents per month
    common_mechanisms: List[str] = field(default_factory=list)
    last_incident_days: int = -1
    runbook_ids: List[str] = field(default_factory=list)


class OrganizationalKnowledgeGraph:
    """
    Stores organizational knowledge about teams, services, and failure patterns.

    This graph allows the investigation system to leverage institutional
    knowledge like "auth-service has had 3 connection pool incidents in
    the last month" or "the payments team's releases frequently cause
    DNS resolution issues."
    """

    def __init__(self) -> None:
        self._teams: Dict[str, TeamProfile] = {}
        self._services: Dict[str, ServiceProfile] = {}
        self._failure_patterns: Dict[str, List[str]] = {}

        # Initialize with baseline organizational data
        self._initialize_baseline()

    def _initialize_baseline(self) -> None:
        """Initialize with known organizational structure."""
        baseline_teams = {
            "payments": TeamProfile(
                team_name="Billing & Core Payments",
                services=["payment-api", "checkout-service"],
                common_failure_modes=["deployment_error", "configuration_drift"],
                known_risks=["connection pool exhaustion after releases"],
            ),
            "identity": TeamProfile(
                team_name="Identity & Security",
                services=["auth-service"],
                common_failure_modes=["dependency_failure", "resource_exhaustion"],
                known_risks=["token cache invalidation during upgrades"],
            ),
            "platform": TeamProfile(
                team_name="API Gateway Infrastructure",
                services=["gateway-service", "api-gateway"],
                common_failure_modes=["cascade_failure", "network_partition"],
                known_risks=["DNS resolver misconfiguration"],
            ),
            "data": TeamProfile(
                team_name="Data Platforms",
                services=["db-service", "analytics-service"],
                common_failure_modes=["resource_exhaustion", "data_corruption"],
            ),
            "engagement": TeamProfile(
                team_name="User Engagement",
                services=["notification-service", "user-service"],
                common_failure_modes=["dependency_failure"],
            ),
        }

        for key, team in baseline_teams.items():
            self._teams[key] = team
            for svc in team.services:
                self._services[svc] = ServiceProfile(
                    service_name=svc,
                    team=team.team_name,
                    common_mechanisms=team.common_failure_modes,
                )

    def get_team_for_service(self, service: str) -> TeamProfile | None:
        """Look up which team owns a service."""
        svc_profile = self._services.get(service)
        if svc_profile:
            for team in self._teams.values():
                if team.team_name == svc_profile.team:
                    return team
        return None

    def get_service_profile(self, service: str) -> ServiceProfile | None:
        return self._services.get(service)

    def get_known_risks(self, service: str) -> List[str]:
        """Get known risk factors for a service."""
        team = self.get_team_for_service(service)
        if team:
            return team.known_risks
        return []

    def get_common_mechanisms(self, service: str) -> List[str]:
        """Get the most common failure mechanisms for a service."""
        profile = self._services.get(service)
        if profile:
            return profile.common_mechanisms
        return []

    def record_incident(
        self,
        service: str,
        mechanism: str,
        resolution_minutes: float = 0.0,
    ) -> None:
        """Record an incident against a service for future learning."""
        profile = self._services.get(service)
        if profile:
            profile.incident_count = getattr(profile, "incident_count", 0) + 1
            if mechanism not in profile.common_mechanisms:
                profile.common_mechanisms.append(mechanism)

        team = self.get_team_for_service(service)
        if team:
            team.incident_count += 1
