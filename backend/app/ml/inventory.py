from collections import defaultdict
from datetime import date
from typing import Dict, List, Tuple

from ..models.forecast import ForecastPoint
from ..models.plan import InventoryConstraints


def summarize_demand(
    points: List[ForecastPoint],
) -> Tuple[Dict[str, float], date | None, date | None]:
    demand_by_sku: Dict[str, float] = defaultdict(float)
    min_date: date | None = None
    max_date: date | None = None

    for p in points:
        demand_by_sku[p.sku] += p.mean
        if min_date is None or p.date < min_date:
            min_date = p.date
        if max_date is None or p.date > max_date:
            max_date = p.date

    return demand_by_sku, min_date, max_date


def compute_safety_stock_for_sku(
    total_demand: float,
    horizon_days: int,
    constraints: InventoryConstraints,
) -> float:
    if horizon_days <= 0:
        return 0.0

    avg_daily = total_demand / float(horizon_days)

    z_value = 1.65 if constraints.target_service_level >= 0.95 else 1.0

    safety_stock = avg_daily * float(constraints.lead_time_days) * z_value
    return safety_stock
