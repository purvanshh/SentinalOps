from jose import jwt

from core.config import get_settings


def make_auth_header(role: str) -> dict[str, str]:
    settings = get_settings()
    payload = {
        "sub": "test-user",
        "roles": [role],
        "aud": settings.auth0_audience,
        "iss": settings.auth_issuer,
    }
    token = jwt.encode(payload, settings.auth0_secret_key, algorithm=settings.auth0_algorithms.split(",")[0].strip())
    return {"Authorization": f"Bearer {token}"}
