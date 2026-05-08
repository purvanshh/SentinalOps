from fastapi import APIRouter

from evaluation.runner import run_evaluation

router = APIRouter(prefix="/evaluations", tags=["evaluations"])


@router.get("/summary")
async def evaluation_summary() -> dict:
    return run_evaluation()
