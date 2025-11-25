from __future__ import annotations

from datetime import date
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel


class PlanObjective(str, Enum):
    service_level = "service_level"
    margin = "margin"
    cost = "cost"


class InventoryConstraints(BaseModel):
    target_service_level: float = 0.95
    max_days_of_cover: int = 90
    min_days_of_cover: int = 0
    lead_time_days: int = 10


class PlanGenerateRequest(BaseModel):
    forecast_id: str
    objective: PlanObjective = PlanObjective.service_level
    constraints: InventoryConstraints = InventoryConstraints()
    location: Optional[str] = None


class RecommendedOrder(BaseModel):
    sku: str
    location: Optional[str]
    order_date: date
    quantity: float
    order_type: str = "purchase"


class ProductionRecommendation(BaseModel):
    sku: str
    line_id: Optional[str]
    production_date: date
    quantity: float


class PlanKPI(BaseModel):
    name: str
    value: float
    unit: Optional[str] = None


class PlanResponse(BaseModel):
    plan_id: str
    forecast_id: str
    orders: List[RecommendedOrder]
    production: List[ProductionRecommendation]
    kpis: List[PlanKPI]
