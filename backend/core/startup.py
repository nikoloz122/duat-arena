"""Production configuration checks at application startup."""

from backend.core.config import settings


def validate_production_config() -> None:
    """Fail fast when production is misconfigured."""
    if not settings.is_production:
        return
    missing: list[str] = []
    if not settings.byoa_key.strip():
        missing.append("DUAT_BYOA_KEY")
    if not settings.arena_api_key.strip():
        missing.append("DUAT_ARENA_API_KEY")
    if missing:
        joined = ", ".join(missing)
        raise RuntimeError(
            f"Production requires: {joined}. "
            "Set these environment variables before starting the server."
        )
