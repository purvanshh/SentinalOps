from jose import jwt

from api.middleware.auth import decode_access_token
from core.config import get_settings


def _make_token(*, roles: list[str], sub: str = "user-1") -> str:
    settings = get_settings()
    payload = {
        "sub": sub,
        "roles": roles,
        "aud": settings.auth0_audience,
        "iss": settings.auth_issuer,
    }
    return jwt.encode(
        payload,
        settings.auth0_secret_key,
        algorithm=settings.auth0_algorithms.split(",")[0].strip(),
    )


def test_decode_access_token_extracts_roles() -> None:
    user = decode_access_token(_make_token(roles=["operator"]))

    assert user.user_id == "user-1"
    assert user.roles == ["operator"]
