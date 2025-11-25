from typing import Optional

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from ..core.config import get_settings


_engine: Optional[Engine] = None


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_engine(settings.database_url)
    return _engine
