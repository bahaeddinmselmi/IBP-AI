from typing import List

from ..models.plan import PlanResponse
from ..models.scenario import ScenarioRequest, ScenarioKPI, ScenarioShockType


def compute_scenario_kpis(
    plan: PlanResponse,
    request: ScenarioRequest,
) -> List[ScenarioKPI]:
    base_volume = sum(o.quantity for o in plan.orders) + sum(
        p.quantity for p in plan.production
    )

    demand_factors = [
        shock.factor
        for shock in request.shocks
        if shock.type == ScenarioShockType.demand
    ]

    if demand_factors:
        demand_factor = sum(demand_factors) / float(len(demand_factors))
    else:
        demand_factor = 1.0

    scenario_volume = base_volume * demand_factor
    delta_volume = scenario_volume - base_volume

    kpis = [
        ScenarioKPI(
            name="Total Volume",
            base=base_volume,
            scenario=scenario_volume,
            delta=delta_volume,
            unit="units",
        )
    ]

    return kpis
