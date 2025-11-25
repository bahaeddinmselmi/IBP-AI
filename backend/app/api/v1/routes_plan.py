from fastapi import APIRouter, Depends

from ...core.security import require_role, UserContext
from ...models.plan import PlanGenerateRequest, PlanResponse
from ...services.planning_service import PlanningService


router = APIRouter(tags=["plan"])


planning_service = PlanningService()


@router.post("/plan/generate", response_model=PlanResponse)
async def generate_plan(
    payload: PlanGenerateRequest,
    user: UserContext = Depends(require_role(["planner", "admin"])),
) -> PlanResponse:
    return planning_service.generate_plan(payload)
