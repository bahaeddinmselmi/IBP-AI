import uuid

from fastapi import HTTPException, status

from ..models.scenario import (
    ScenarioRequest,
    ScenarioResponse,
    ScenarioSummary,
    ScenarioListResponse,
    ScenarioShockType,
)
from .store import store
from ..ml.scenario import compute_scenario_kpis


class ScenarioService:
    def run_scenario(self, payload: ScenarioRequest) -> ScenarioResponse:
        plan = None

        if payload.plan_id:
            plan = store.plans.get(payload.plan_id)
            if plan is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Plan not found",
                )
        else:
            for candidate in store.plans.values():
                if candidate.forecast_id == payload.forecast_id:
                    plan = candidate
                    break

        if plan is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No base plan available for scenario",
            )

        kpis = compute_scenario_kpis(plan, payload)

        # Simple narrative generation based on demand shocks and total volume KPI
        demand_factors = [
            shock.factor
            for shock in payload.shocks
            if shock.type == ScenarioShockType.demand
        ]
        if demand_factors:
            avg_demand_factor = sum(demand_factors) / float(len(demand_factors))
        else:
            avg_demand_factor = 1.0

        total_kpi = next((k for k in kpis if k.name == "Total Volume"), None)
        narrative_parts: list[str] = []
        if total_kpi is not None:
            if total_kpi.base != 0:
                pct_change = (total_kpi.delta / total_kpi.base) * 100.0
            else:
                pct_change = 0.0
            if total_kpi.delta > 0:
                direction = "increase"
            elif total_kpi.delta < 0:
                direction = "decrease"
            else:
                direction = "no change"

            narrative_parts.append(
                f"Total volume {direction} from {total_kpi.base:.0f} to "
                f"{total_kpi.scenario:.0f} units ({pct_change:+.1f}%)."
            )

        if avg_demand_factor != 1.0:
            narrative_parts.append(
                f"Average demand factor applied across shocks: x{avg_demand_factor:.2f}."
            )

        narrative = None
        if narrative_parts:
            scenario_name = payload.name or "Scenario"
            narrative = f"{scenario_name}: " + " ".join(narrative_parts)

        scenario_id = str(uuid.uuid4())
        response = ScenarioResponse(
            scenario_id=scenario_id,
            forecast_id=payload.forecast_id,
            plan_id=plan.plan_id,
            name=payload.name,
            kpis=kpis,
            narrative=narrative,
        )
        store.scenarios[scenario_id] = response
        return response

    def list_scenarios(
        self,
        forecast_id: str | None = None,
        plan_id: str | None = None,
    ) -> ScenarioListResponse:
        items: list[ScenarioSummary] = []

        for scenario in store.scenarios.values():
            if forecast_id is not None and scenario.forecast_id != forecast_id:
                continue
            if plan_id is not None and scenario.plan_id != plan_id:
                continue

            items.append(
                ScenarioSummary(
                    scenario_id=scenario.scenario_id,
                    forecast_id=scenario.forecast_id,
                    plan_id=scenario.plan_id,
                    name=scenario.name,
                )
            )

        return ScenarioListResponse(scenarios=items)

    def get_scenario(self, scenario_id: str) -> ScenarioResponse:
        scenario = store.scenarios.get(scenario_id)
        if scenario is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Scenario not found",
            )
        return scenario
