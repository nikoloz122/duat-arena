"""Record a one-command LLM-vs-baseline demo run.

Runs the real LLM agent alongside a deterministic ConservativeAgent baseline
through one DeFi catastrophe scenario, writing the standard replay + manifest +
summary sidecars into the configured log dir (the same place the API/dashboard
read). It is a thin wrapper around the engine — no new engine, scoring, or
scenario logic.

Cost / determinism: the first run performs one pass of live API calls and
records every LLM response to the deterministic cache. Any later run with the
same scenario + ticks hits the cache and makes ZERO API calls, producing an
identical replay body. With no key and no cache, the LLM agent degrades to safe
holds and this script still completes.

Usage:
    python scripts/record_llm_demo.py
    python scripts/record_llm_demo.py --scenario stablecoin-depeg --ticks 30
"""

import argparse
import os
import sys
from pathlib import Path

# Allow running as a plain script (python scripts/record_llm_demo.py).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agents.llm_agent import LLM_AGENT_ID, build_llm_agent
from agents.templates import ConservativeAgent
from backend.core.config import settings
from scenarios.registry import DEFAULT_SCENARIO_ID, get_scenario
from simulation.engine import SimulationEngine
from simulation.replay import ReplayRecorder

DEFAULT_DEMO_SCENARIO = "liquidation-cascade"
DEFAULT_DEMO_TICKS = 30


def record(scenario_id: str, ticks: int) -> dict:
    """Run the LLM agent vs the baseline once and return the simulation result dict."""
    agents = [build_llm_agent(), ConservativeAgent()]
    engine = SimulationEngine(
        agents=agents,
        scenario=get_scenario(scenario_id),
        max_ticks=ticks,
        recorder=ReplayRecorder(log_dir=settings.replay_log_dir),
    )
    return engine.run().to_dict()


def _print_report(result: dict) -> None:
    integrity_by_id = {
        report.get("agent_id"): report.get("decision_integrity_events", 0)
        for report in result.get("agent_reports", [])
    }

    print(f"Scenario: {result.get('scenario')}  ({result.get('ticks')} ticks)")
    print(f"Replay id: {result.get('replay_id')}")
    print("Reliability:")
    for report in result.get("reliability_reports", []):
        agent_id = report.get("agent_id")
        interventions = integrity_by_id.get(agent_id, 0)
        print(
            f"  - {agent_id}: score {report.get('score')} "
            f"(grade {report.get('grade')}), "
            f"decision-boundary interventions: {interventions}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Record an LLM-vs-baseline demo run.")
    parser.add_argument("--scenario", default=DEFAULT_DEMO_SCENARIO, help="Scenario id")
    parser.add_argument("--ticks", type=int, default=DEFAULT_DEMO_TICKS, help="Tick count")
    args = parser.parse_args()

    scenario_id = args.scenario if args.scenario in _known_scenarios() else DEFAULT_DEMO_SCENARIO

    if not os.getenv("ANTHROPIC_API_KEY"):
        print(
            "Notice: ANTHROPIC_API_KEY not set. The LLM agent will use the cache "
            "if present, otherwise degrade to safe holds (no API calls)."
        )

    result = record(scenario_id, max(5, args.ticks))
    _print_report(result)
    print(
        "\nFirst run records the cache (one pass of live calls); re-running the "
        "same scenario + ticks replays from cache with zero API calls."
    )


def _known_scenarios() -> set:
    # Local import keeps the module import surface minimal.
    from scenarios.registry import scenario_ids

    ids = set(scenario_ids())
    ids.add(DEFAULT_SCENARIO_ID)
    return ids


if __name__ == "__main__":
    main()
