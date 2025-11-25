from fastapi import APIRouter, Depends

from ...core.security import require_role, UserContext
from ...models.scenario import (
    ScenarioRequest,
    ScenarioResponse,
    ScenarioListResponse,
)
from ...services.scenario_service import ScenarioService


router = APIRouter(tags=["scenario"])


scenario_service = ScenarioService()


@router.post("/scenario", response_model=ScenarioResponse)
async def run_scenario(
    payload: ScenarioRequest,
    user: UserContext = Depends(require_role(["planner", "admin"])),
) -> ScenarioResponse:
    return scenario_service.run_scenario(payload)


@router.get("/scenario", response_model=ScenarioListResponse)
async def list_scenarios(
    forecast_id: str | None = None,
    plan_id: str | None = None,
    user: UserContext = Depends(require_role(["planner", "admin", "viewer"])),
) -> ScenarioListResponse:
    return scenario_service.list_scenarios(forecast_id=forecast_id, plan_id=plan_id)


@router.get("/scenario/{scenario_id}", response_model=ScenarioResponse)
async def get_scenario(
    scenario_id: str,
    user: UserContext = Depends(require_role(["planner", "admin", "viewer"])),
) -> ScenarioResponse:
    return scenario_service.get_scenario(scenario_id)
