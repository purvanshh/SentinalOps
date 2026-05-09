from datetime import UTC, datetime, timedelta

from tools.execution_guard import create_approval_token, decode_approval_token


def test_create_and_decode_approval_token_round_trip() -> None:
    token = create_approval_token(
        incident_id="incident-1",
        action_ids=["restart_service"],
        approved_by="operator-1",
        expires_at=datetime.now(UTC) + timedelta(minutes=10),
    )

    payload = decode_approval_token(token)

    assert payload["incident_id"] == "incident-1"
    assert payload["action_ids"] == ["restart_service"]
    assert payload["approved_by"] == "operator-1"
