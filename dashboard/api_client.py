import os
from typing import Any

import requests

DEFAULT_BASE_URL = "http://localhost:8000"
TIMEOUT_SECONDS = 30


def _base_url() -> str:
    return os.getenv("DUAT_API_BASE_URL", DEFAULT_BASE_URL).rstrip("/")


def list_scenarios() -> list[dict[str, Any]]:
    response = requests.get(f"{_base_url()}/api/scenarios", timeout=TIMEOUT_SECONDS)
    response.raise_for_status()
    return response.json()


def list_agents() -> list[dict[str, Any]]:
    response = requests.get(f"{_base_url()}/api/agents", timeout=TIMEOUT_SECONDS)
    response.raise_for_status()
    return response.json()


def run_simulation(
    scenario_id: str,
    ticks: int,
    agent_count: int = 3,
    agent_ids: list[str] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "scenario_id": scenario_id,
        "ticks": ticks,
        "agent_count": agent_count,
    }
    # Only send agent_ids when the caller selected explicit agents, so the
    # backend keeps its default preset behavior otherwise.
    if agent_ids:
        payload["agent_ids"] = agent_ids
    response = requests.post(
        f"{_base_url()}/api/simulations/run",
        json=payload,
        timeout=TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    return response.json()


def get_replay(replay_id: str) -> dict[str, Any]:
    response = requests.get(
        f"{_base_url()}/api/replays/{replay_id}",
        timeout=TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    return response.json()


def list_replays() -> list[dict[str, Any]]:
    response = requests.get(f"{_base_url()}/api/replays", timeout=TIMEOUT_SECONDS)
    response.raise_for_status()
    return response.json()


def compare_replays(replay_ids: list[str]) -> dict[str, Any]:
    response = requests.post(
        f"{_base_url()}/api/replays/compare",
        json={"replay_ids": replay_ids},
        timeout=TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    return response.json()
