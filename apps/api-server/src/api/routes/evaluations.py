from api.dependencies import require_role
from api.middleware.auth import AuthenticatedUser
from evaluation.runner import run_evaluation
from fastapi import APIRouter, Depends

router = APIRouter(prefix="/evaluations", tags=["evaluations"])
VIEWER_ROLE_DEPENDENCY = Depends(require_role(["viewer"]))


@router.get("/summary")
async def evaluation_summary(
    _: AuthenticatedUser = VIEWER_ROLE_DEPENDENCY,
) -> dict:
    return await run_evaluation()
