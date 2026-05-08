from jose import jwt


def make_auth_header(role: str) -> dict[str, str]:
    payload = {
        "sub": "test-user",
        "roles": [role],
        "aud": "sentinelops-api",
        "iss": "https://sentinelops.local/",
    }
    token = jwt.encode(payload, "dev-secret-change-me", algorithm="HS256")
    return {"Authorization": f"Bearer {token}"}
