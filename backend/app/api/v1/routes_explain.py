from fastapi import APIRouter, Depends

from ...core.security import require_role, UserContext
from ...models.explain import ExplainResponse
from ...services.explainability_service import ExplainabilityService


router = APIRouter(tags=["explain"])


explain_service = ExplainabilityService()


@router.get("/explain/{forecast_id}", response_model=ExplainResponse)
async def explain_forecast(
    forecast_id: str,
    user: UserContext = Depends(require_role(["planner", "admin", "viewer"])),
) -> ExplainResponse:
    return explain_service.explain_forecast(forecast_id)
