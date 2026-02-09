"""
API security helpers.
"""
from typing import Optional
from fastapi import Header, HTTPException, status

from app.core.config import settings


async def require_api_key(x_api_key: Optional[str] = Header(default=None, alias="X-API-Key")):
    """Require an API key when API auth is enabled."""
    if not settings.API_AUTH_ENABLED:
        return

    if not settings.API_AUTH_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="API auth is enabled but API_AUTH_TOKEN is not configured"
        )

    if x_api_key != settings.API_AUTH_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key"
        )
