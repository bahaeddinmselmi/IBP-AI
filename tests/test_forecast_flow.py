from datetime import date

from fastapi.testclient import TestClient

from backend.app.main import app


client = TestClient(app)

API_HEADERS = {"X-API-Key": "dev-api-key-change-me"}


def test_forecast_plan_scenario_and_explain() -> None:
    forecast_payload = {
        "sku_list": ["SKU-001", "SKU-002"],
        "start_date": date(2025, 1, 1).isoformat(),
        "end_date": date(2025, 1, 7).isoformat(),
        "granularity": "D",
        "location": "WH-1",
    }

    r_forecast = client.post("/api/v1/forecast", json=forecast_payload, headers=API_HEADERS)
    assert r_forecast.status_code == 200
    forecast = r_forecast.json()
    forecast_id = forecast["forecast_id"]
    assert forecast["points"]

    plan_payload = {
        "forecast_id": forecast_id,
        "objective": "service_level",
        "constraints": {
            "target_service_level": 0.95,
            "max_days_of_cover": 90,
            "min_days_of_cover": 0,
            "lead_time_days": 10,
        },
        "location": "WH-1",
    }

    r_plan = client.post("/api/v1/plan/generate", json=plan_payload, headers=API_HEADERS)
    assert r_plan.status_code == 200
    plan = r_plan.json()
    plan_id = plan["plan_id"]

    r_explain = client.get(f"/api/v1/explain/{forecast_id}", headers=API_HEADERS)
    assert r_explain.status_code == 200
    explain = r_explain.json()
    assert explain["forecast_id"] == forecast_id
    assert explain["global_importance"]

    scenario_payload = {
        "forecast_id": forecast_id,
        "plan_id": plan_id,
        "name": "Demand x1.2",
        "shocks": [
            {
                "type": "demand",
                "sku": None,
                "location": None,
                "start_date": date(2025, 1, 1).isoformat(),
                "end_date": date(2025, 1, 7).isoformat(),
                "factor": 1.2,
                "delta": 0.0,
            }
        ],
    }

    r_scenario = client.post("/api/v1/scenario", json=scenario_payload, headers=API_HEADERS)
    assert r_scenario.status_code == 200
    scenario = r_scenario.json()
    assert scenario["kpis"]
