from fastapi import APIRouter, Depends

from ...core.security import require_role, UserContext
from ...models.forecast import ForecastRequest, ForecastResponse
from ...services.forecasting_service import ForecastService


router = APIRouter(tags=["forecast"])


forecast_service = ForecastService()


@router.post("/forecast", response_model=ForecastResponse)
async def create_forecast(
    payload: ForecastRequest,
    user: UserContext = Depends(require_role(["planner", "admin"])),
) -> ForecastResponse:
    return forecast_service.generate_forecast(payload)
