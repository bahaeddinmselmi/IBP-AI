from fastapi import HTTPException, status

from ..models.explain import ExplainResponse
from .store import store
from ..ml.explainability import build_explanation


class ExplainabilityService:
    def explain_forecast(self, forecast_id: str) -> ExplainResponse:
        forecast = store.forecasts.get(forecast_id)
        if forecast is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Forecast not found",
            )

        return build_explanation(forecast)
