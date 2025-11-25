import uuid

from fastapi import HTTPException, status

from ..models.plan import PlanGenerateRequest, PlanResponse
from .store import store
from ..ml.supply_planning import generate_supply_plan


class PlanningService:
    def generate_plan(self, payload: PlanGenerateRequest) -> PlanResponse:
        forecast = store.forecasts.get(payload.forecast_id)
        if forecast is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Forecast not found",
            )

        orders, production, kpis = generate_supply_plan(
            forecast.points,
            payload.constraints,
            payload.location,
        )

        plan_id = str(uuid.uuid4())
        response = PlanResponse(
            plan_id=plan_id,
            forecast_id=payload.forecast_id,
            orders=orders,
            production=production,
            kpis=kpis,
        )
        store.plans[plan_id] = response
        return response
