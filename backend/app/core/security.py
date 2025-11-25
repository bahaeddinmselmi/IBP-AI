from fastapi import Header, HTTPException, status, Depends
from typing import Optional

from .config import get_settings


class UserContext:
    def __init__(self, api_key: str, role: str):
        self.api_key = api_key
        self.role = role


async def get_current_user(
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
    x_role: Optional[str] = Header(default=None, alias="X-Role"),
) -> UserContext:
    settings = get_settings()

    if x_api_key is None or x_api_key != settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )

    role = x_role or settings.default_role
    if role not in settings.allowed_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Role not allowed",
        )

    return UserContext(api_key=x_api_key, role=role)


def require_role(required_roles: list[str]):
    async def _dependency(user: UserContext = Depends(get_current_user)) -> UserContext:
        if user.role not in required_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return user

    return _dependency
