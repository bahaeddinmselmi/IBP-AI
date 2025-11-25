from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel


class FeatureContribution(BaseModel):
    feature: str
    importance: float
    direction: str


class SKUExplanation(BaseModel):
    sku: str
    top_drivers: List[FeatureContribution]


class ExplainResponse(BaseModel):
    forecast_id: str
    global_importance: List[FeatureContribution]
    by_sku: List[SKUExplanation]
    method: str = "stub-shap-like"
    external_summary: Optional[str] = None
