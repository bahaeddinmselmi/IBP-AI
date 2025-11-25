# IBP AI Planning Platform

AI-powered Integrated Business Planning (IBP) SaaS skeleton. This project provides a modular, end-to-end example of:

- **SKU-level probabilistic forecasting** (ensemble stub of ARIMA/Prophet/XGBoost/deep models)
- **Inventory optimization** (safety stock, reorder suggestion)
- **Supply planning** (simple capacity-unaware planning)
- **Scenario simulation** (demand/supply/capacity shocks)
- **Control tower & explainability hooks** (to be consumed by the frontend)
- **MLOps-ready structure** (MLflow hooks, retraining scripts skeleton)

This codebase is designed as a clean, extensible starting point rather than a finished enterprise system.

---

## Project Structure

```text
IBP_ai/
  README.md
  requirements.txt
  backend/
    app/
      __init__.py
      main.py
      core/
        __init__.py
        config.py
        security.py
      api/
        __init__.py
        v1/
          __init__.py
          routes_forecast.py
          routes_plan.py
          routes_explain.py
          routes_scenario.py
      models/
        __init__.py
        forecast.py
        plan.py
        scenario.py
        explain.py
      services/
        __init__.py
        forecasting_service.py
        planning_service.py
        scenario_service.py
        explainability_service.py
        alert_service.py
      ml/
        __init__.py
        forecasting.py
        inventory.py
        supply_planning.py
        scenario.py
        explainability.py
  data/
    sample_sales.csv
    sample_inventory.csv
    sample_production.csv
    sample_purchase_orders.csv
    sample_master_data.csv
    sample_external_signals.csv
  frontend/
    (Streamlit app will be added in the next step)
  mlops/
    (training, retraining, monitoring scripts will be added)
  deployments/
    (Dockerfile, Render config, etc. will be added)
  tests/
    (basic tests will be added)
```

---

## Requirements

- Python **3.10+** (intended to work with 3.13 as libraries catch up)
- `pip` or `uv`/`poetry` for dependency management

Install dependencies:

```bash
pip install -r requirements.txt
```

---

## Running the Backend (FastAPI)

```bash
# From the project root
uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`.

Interactive docs:

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

### Authentication

All main endpoints require an API key header:

- `X-API-Key: dev-api-key-change-me` (default, configurable via `IBP_API_KEY` env var)
- Optional role header for RBAC tagging: `X-Role: admin|planner|viewer` (default: `planner`)

---

## Core API Endpoints

- `POST /api/v1/forecast`
  - Inputs: SKU list, date range, granularity, optional external signals.
  - Output: probabilistic forecast (mean, q10, q50, q90) per SKU, with model metadata.

- `POST /api/v1/plan/generate`
  - Inputs: `forecast_id`, planning objective, basic inventory constraints.
  - Output: recommended purchase orders, production plan, and simple KPIs.

- `GET /api/v1/explain/{forecast_id}`
  - Output: SHAP/LIME-style stub explanation with top drivers per SKU.

- `POST /api/v1/scenario`
  - Inputs: `forecast_id`, optional `plan_id`, list of demand/supply/capacity shocks.
  - Output: scenario KPIs vs base plan.

- `GET /health`
  - Simple health check.

---

## Sample Data

`data/` contains small synthetic CSVs for:

- **Sales transactions**: `sample_sales.csv`
- **Inventory snapshots**: `sample_inventory.csv`
- **Production capacity**: `sample_production.csv`
- **Purchase orders**: `sample_purchase_orders.csv`
- **Master data**: `sample_master_data.csv`
- **External signals**: `sample_external_signals.csv`

These are suitable for quick experiments and unit tests; for real deployments you would connect to PostgreSQL and external sources.

---

## Frontend (Streamlit Dashboard)

A Streamlit control-tower dashboard will be provided under `frontend/` that:

- Shows forecast vs actual
- Shows inventory vs recommended
- Highlights top-risk SKUs
- Allows running scenarios via simple sliders/presets

Run (after the frontend file is added):

```bash
streamlit run frontend/streamlit_app.py
```

---

## MLOps & Deployment (to be filled)

- **MLflow** hooks in training scripts for model registry and experiment tracking.
- **Retraining pipeline** skeleton using simple Python scripts / schedulers.
- **Dockerfile** and optional Render/AWS/GCP configuration for cloud deployment.

These will be added as separate modules so you can extend them with your own infra.

---

## Next Steps

- Extend the stub ensemble to real ARIMA/Prophet/XGBoost/Deep models.
- Replace in-memory stores with PostgreSQL + object storage (e.g., S3/Parquet).
- Harden security (multi-tenant RBAC, JWT, audit logging).
- Integrate real external signals (promotions, holidays, weather, Google Trends).
- Build full production-grade retraining and monitoring pipelines.
