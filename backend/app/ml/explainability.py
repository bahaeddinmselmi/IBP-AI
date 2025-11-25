from typing import List

from ..models.explain import (
    ExplainResponse,
    FeatureContribution,
    SKUExplanation,
)
from ..integrations.external_signals import summarize_signals
from ..models.forecast import ForecastResponse


def build_explanation(forecast: ForecastResponse) -> ExplainResponse:
    features = [
        "trend",
        "seasonality",
        "promotion",
        "holiday",
        "price",
        "weather",
    ]

    base_weights = [0.3, 0.25, 0.2, 0.1, 0.1, 0.05]

    global_importance: List[FeatureContribution] = []
    for feature, weight in zip(features, base_weights):
        direction = "positive"
        if feature in {"price", "weather"}:
            direction = "negative"
        global_importance.append(
            FeatureContribution(
                feature=feature,
                importance=weight,
                direction=direction,
            )
        )

    skus = sorted({p.sku for p in forecast.points})

    by_sku: List[SKUExplanation] = []

    for index, sku in enumerate(skus):
        adjusted_drivers: List[FeatureContribution] = []
        scale = 1.0 + 0.05 * float(index)
        for contribution in global_importance:
            adjusted_drivers.append(
                FeatureContribution(
                    feature=contribution.feature,
                    importance=contribution.importance * scale,
                    direction=contribution.direction,
                )
            )
        by_sku.append(
            SKUExplanation(
                sku=sku,
                top_drivers=adjusted_drivers,
            )
        )

    external_text = summarize_signals(location=None)

    response = ExplainResponse(
        forecast_id=forecast.forecast_id,
        global_importance=global_importance,
        by_sku=by_sku,
        method="stub-shap-like",
        external_summary=external_text or None,
    )

    return response
