"""Seed a few deterministic demo runs so the dashboard has history on first use.

This drives the real `SimulationEngine` with the preset agents across a handful
of scenarios and writes the standard replay JSONL plus manifest and summary
sidecars into the configured replay log dir (the same place the API reads). It
adds no new behavior: it is just a thin convenience wrapper around the engine.

Determinism: the engine and preset agents are deterministic, so the same
scenario + tick count always produces identical replay bodies. Run ids carry a
timestamp (so re-runs append rather than collide), but the recorded events are
reproducible.

Usage:
    python scripts/seed_demo.py
"""

import sys
from pathlib import Path

# Allow running as a plain script (python scripts/seed_demo.py) by ensuring the
# project root is importable.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agents.templates import build_default_agents
from backend.core.config import settings
from scenarios.registry import get_scenario
from simulation.engine import SimulationEngine
from simulation.replay import ReplayRecorder

# Scenarios to seed. A spread of failure shapes makes the comparison view
# meaningful immediately (a survivable shock, a cascade, and a slow depeg).
SEED_SCENARIOS = ("flash-crash", "liquidation-cascade", "stablecoin-depeg")
SEED_TICKS = 30


def seed() -> list[str]:
    """Generate one run per seed scenario. Returns the created replay ids."""
    replay_ids: list[str] = []
    for scenario_id in SEED_SCENARIOS:
        engine = SimulationEngine(
            agents=build_default_agents(),
            scenario=get_scenario(scenario_id),
            max_ticks=SEED_TICKS,
            recorder=ReplayRecorder(log_dir=settings.replay_log_dir),
        )
        result = engine.run()
        replay_ids.append(result.replay_id)
    return replay_ids


def main() -> None:
    replay_ids = seed()
    print(f"Seeded {len(replay_ids)} demo run(s) into '{settings.replay_log_dir}':")
    for replay_id in replay_ids:
        print(f"  - {replay_id}")
    print("Open the dashboard and use 'Compare Past Runs' to see them.")


if __name__ == "__main__":
    main()
