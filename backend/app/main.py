import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .core.config import get_settings
from .api.v1.routes_forecast import router as forecast_router
from .api.v1.routes_plan import router as plan_router
from .api.v1.routes_explain import router as explain_router
from .api.v1.routes_scenario import router as scenario_router
from .api.v1.routes_data import router as data_router
from .api.v1.routes_copilot import router as copilot_router


# Configure logging to show INFO level messages
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

settings = get_settings()

app = FastAPI(title=settings.app_name)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.get("/")
async def root() -> dict:
    return {"app": settings.app_name, "api_v1_prefix": settings.api_v1_prefix}


app.include_router(forecast_router, prefix=settings.api_v1_prefix)
app.include_router(plan_router, prefix=settings.api_v1_prefix)
app.include_router(explain_router, prefix=settings.api_v1_prefix)
app.include_router(scenario_router, prefix=settings.api_v1_prefix)
app.include_router(data_router, prefix=settings.api_v1_prefix)
app.include_router(copilot_router, prefix=settings.api_v1_prefix)
