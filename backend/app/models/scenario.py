from __future__ import annotations

from datetime import date
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel


class ScenarioShockType(str, Enum):
    demand = "demand"
    supply = "supply"
    capacity = "capacity"
    price = "price"


class ScenarioShock(BaseModel):
    type: ScenarioShockType
    sku: Optional[str] = None
    location: Optional[str] = None
    start_date: date
    end_date: date
    factor: float = 1.0
    delta: float = 0.0


class ScenarioRequest(BaseModel):
    forecast_id: str
    plan_id: Optional[str] = None
    name: Optional[str] = None
    shocks: List[ScenarioShock]


class ScenarioKPI(BaseModel):
    name: str
    base: float
    scenario: float
    delta: float
    unit: Optional[str] = None


class ScenarioResponse(BaseModel):
    scenario_id: str
    forecast_id: str
    plan_id: Optional[str] = None
    name: Optional[str] = None
    kpis: List[ScenarioKPI]
    narrative: Optional[str] = None


class ScenarioSummary(BaseModel):
    scenario_id: str
    forecast_id: str
    plan_id: Optional[str] = None
    name: Optional[str] = None


class ScenarioListResponse(BaseModel):
    scenarios: List[ScenarioSummary]
