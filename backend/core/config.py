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


settings = Settings()