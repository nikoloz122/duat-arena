import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv("APP_NAME", "DUAT Arena")
    app_version: str = os.getenv("APP_VERSION", "0.1.0")
    app_description: str = os.getenv(
        "APP_DESCRIPTION",
        "Stress testing for trading bots and AI agents — deterministic DeFi chaos scenarios with explainable reliability grades.",
    )
    replay_log_dir: str = os.getenv("REPLAY_LOG_DIR", "logs")
    environment: str = os.getenv("ENVIRONMENT", "development")
    # Protect BYOA management routes on shared deployments (optional in local dev).
    arena_api_key: str = os.getenv("DUAT_ARENA_API_KEY", "")
    # Required when ENVIRONMENT=production — encrypts stored agent credentials.
    byoa_key: str = os.getenv("DUAT_BYOA_KEY", "")
    byoa_test_rate_limit: int = int(os.getenv("DUAT_BYOA_TEST_RATE_LIMIT", "20"))
    byoa_test_rate_window_seconds: float = float(
        os.getenv("DUAT_BYOA_TEST_RATE_WINDOW_SECONDS", "60")
    )

    @property
    def is_production(self) -> bool:
        return self.environment.strip().lower() == "production"


settings = Settings()
