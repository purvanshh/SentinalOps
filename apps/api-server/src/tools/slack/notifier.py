from tools.slack.client import SlackClient


async def notify_approval_required(incident_id: str, summary: str) -> None:
    client = SlackClient()
    await client.send_message(
        f"SentinelOps incident {incident_id} is awaiting approval.\n{summary}"
    )


async def notify_approval_escalation(incident_id: str, reason: str) -> None:
    client = SlackClient()
    await client.send_message(
        f"Approval escalation for incident {incident_id}: {reason}"
    )
