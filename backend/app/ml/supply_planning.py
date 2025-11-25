from datetime import date
from typing import List, Tuple, Optional

from ..models.forecast import ForecastPoint
from ..models.plan import (
    InventoryConstraints,
    RecommendedOrder,
    ProductionRecommendation,
    PlanKPI,
)
from .inventory import summarize_demand, compute_safety_stock_for_sku


def generate_supply_plan(
    points: List[ForecastPoint],
    constraints: InventoryConstraints,
    location: Optional[str],
) -> Tuple[List[RecommendedOrder], List[ProductionRecommendation], List[PlanKPI]]:
    demand_by_sku, min_date, max_date = summarize_demand(points)

    if min_date is None or max_date is None:
        return [], [], []

    horizon_days = (max_date - min_date).days + 1

    orders: List[RecommendedOrder] = []
    production: List[ProductionRecommendation] = []

    total_volume = 0.0

    for sku, total_demand in demand_by_sku.items():
        safety_stock = compute_safety_stock_for_sku(
            total_demand,
            horizon_days,
            constraints,
        )
        total_required = total_demand + safety_stock

        purchase_quantity = total_required * 0.4
        production_quantity = total_required * 0.6

        if purchase_quantity > 0.0:
            orders.append(
                RecommendedOrder(
                    sku=sku,
                    location=location,
                    order_date=min_date,
                    quantity=purchase_quantity,
                    order_type="purchase",
                )
            )

        if production_quantity > 0.0:
            production.append(
                ProductionRecommendation(
                    sku=sku,
                    line_id="LINE-1",
                    production_date=min_date,
                    quantity=production_quantity,
                )
            )

        total_volume += total_required

    kpis: List[PlanKPI] = [
        PlanKPI(name="Total Volume", value=total_volume, unit="units"),
        PlanKPI(
            name="Target Service Level",
            value=constraints.target_service_level,
            unit="",
        ),
    ]

    return orders, production, kpis
