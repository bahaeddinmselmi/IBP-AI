from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class TimeGranularity(str, Enum):
    day = "D"
    week = "W"
    month = "M"


class ForecastRequest(BaseModel):
    sku_list: List[str] = Field(..., description="List of SKU identifiers")
    start_date: date
    end_date: date
    granularity: TimeGranularity = TimeGranularity.day
    location: Optional[str] = None
    external_signals: Optional[Dict[str, Any]] = None
    # Optional override for model selection: one of arima, prophet, xgboost, stub (baseline)
    forced_model: Optional[str] = None


class ForecastPoint(BaseModel):
    sku: str
    date: date
    mean: float
    q10: float
    q50: float
    q90: float


class ForecastMetadata(BaseModel):
    model_name: str
    model_version: str
    components: List[str] = []
    notes: Optional[str] = None
    per_sku_model: Optional[Dict[str, str]] = None


class ForecastResponse(BaseModel):
    forecast_id: str
    points: List[ForecastPoint]
    metadata: ForecastMetadata
    metrics: Optional[Dict[str, float]] = None
