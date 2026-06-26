"""Optional API-key gate for BYOA management endpoints."""

from fastapi import Header, HTTPException

from backend.core.config import settings

ARENA_API_HEADER = "X-DUAT-Api-Key"


async def require_arena_api_key(
    x_duat_api_key: str | None = Header(default=None, alias=ARENA_API_HEADER),
) -> None:
    """When ``DUAT_ARENA_API_KEY`` is configured, require a matching header."""
    expected = settings.arena_api_key.strip()
    if not expected:
        return
    if not x_duat_api_key or x_duat_api_key != expected:
        raise HTTPException(status_code=401, detail="Invalid or missing Arena API key")
