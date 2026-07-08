from __future__ import annotations


class CodeOwnershipManager:
    """Manages service code ownership and responsible developer teams."""

    def __init__(self) -> None:
        self.ownership = {
            "payment-api": "Billing & Core Payments",
            "auth-service": "Identity & Security",
            "gateway-service": "API Gateway Infrastructure",
            "db-service": "Data Platforms",
            "notification-service": "User Engagement",
        }

    def get_owner_team(self, service: str) -> str:
        return self.ownership.get(service, "Platform Engineering")
