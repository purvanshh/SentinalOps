from fastapi import APIRouter, status

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/refresh", status_code=status.HTTP_200_OK)
async def refresh_token() -> dict[str, str]:
    return {"access_token": "refreshed-token-mock", "token_type": "bearer"}


@router.post("/revoke", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_token() -> None:
    pass
