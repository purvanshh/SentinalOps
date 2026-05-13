from fastapi import APIRouter, Depends

from api.dependencies import require_role
from api.middleware.auth import AuthenticatedUser
from evaluation.runner import run_evaluation

router = APIRouter(prefix="/evaluations", tags=["evaluations"])


@router.get("/summary")
async def evaluation_summary(
    _: AuthenticatedUser = Depends(require_role(["viewer"])),
) -> dict:
    return await run_evaluation()
