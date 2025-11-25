import uuid
from typing import Tuple, Dict, List

from ..models.forecast import (
    ForecastRequest,
    ForecastResponse,
    ForecastPoint,
    ForecastMetadata,
)
from ..ml.forecasting import generate_ensemble_forecast
from .store import store


class ForecastService:
    def generate_forecast(self, payload: ForecastRequest) -> ForecastResponse:
        points, metadata, metrics = generate_ensemble_forecast(payload)
        forecast_id = str(uuid.uuid4())
        response = ForecastResponse(
            forecast_id=forecast_id,
            points=points,
            metadata=metadata,
            metrics=metrics,
        )
        store.forecasts[forecast_id] = response
        return response
