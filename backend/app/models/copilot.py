from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class CopilotContext(str, Enum):
    forecast = "forecast"
    plan = "plan"
    scenario = "scenario"
    data = "data"


class CopilotQueryRequest(BaseModel):
    query: str
    contexts: List[CopilotContext]
    forecast_id: Optional[str] = None
    plan_id: Optional[str] = None
    scenario_id: Optional[str] = None
    dataset_type: Optional[str] = None


class CopilotQueryResponse(BaseModel):
    answer: str
    suggested_actions: List[str] = []
    used_context: Dict[str, Any] = {}
