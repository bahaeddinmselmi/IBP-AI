import os
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    app_name: str = "IBP AI Planning Platform"
    api_v1_prefix: str = "/api/v1"

    api_key: str = os.getenv("IBP_API_KEY", "dev-api-key-change-me")

    # Security / RBAC
    allowed_roles: tuple[str, ...] = ("admin", "planner", "viewer")
    default_role: str = "planner"

    # Storage (placeholders – wire to Postgres/S3 in real deployments)
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./ibp_ai.db")

    # MLOps / tracking
    mlflow_tracking_uri: str | None = os.getenv("MLFLOW_TRACKING_URI")

    # External AI providers
    groq_api_key: str | None = os.getenv("GROQ_API_KEY")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
