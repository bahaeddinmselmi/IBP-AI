from typing import Dict

from ..models.forecast import ForecastResponse
from ..models.plan import PlanResponse
from ..models.scenario import ScenarioResponse


class InMemoryStore:
    def __init__(self) -> None:
        self.forecasts: Dict[str, ForecastResponse] = {}
        self.plans: Dict[str, PlanResponse] = {}
        self.scenarios: Dict[str, ScenarioResponse] = {}


store = InMemoryStore()
