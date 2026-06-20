"""A deliberately broken agent must not crash a run or corrupt its output.

This exercises the engine's safety boundary end-to-end: an agent that raises,
returns junk, and returns non-finite values runs alongside a clean baseline.
The run must complete, record integrity events, and produce a valid result.
"""

import math

from agents.base import AgentDecision, TradingAgent
from agents.templates import ConservativeAgent
from scenarios.registry import get_scenario
from simulation.decision_normalizer import ALLOWED_ACTIONS, MAX_SIZE
from simulation.engine import SimulationEngine, SimulationResult
from simulation.replay import ReplayRecorder


class MalfunctioningAgent(TradingAgent):
    """Cycles through every failure mode the boundary must absorb."""

    def __init__(self) -> None:
        super().__init__("agent-chaos-001", risk_profile="chaos", name="Chaos Agent")

    def decide(self, tick: int, market_state):
        mode = tick % 4
        if mode == 0:
            raise RuntimeError("intentional agent crash")
        if mode == 1:
            return {"action": "moon", "size": float("nan"), "confidence": "high"}
        if mode == 2:
            return ["not", "a", "decision"]
        return AgentDecision(action="buy", size=float("inf"), confidence=5.0)


def _run(tmp_path, ticks: int = 16) -> SimulationResult:
    engine = SimulationEngine(
        agents=[MalfunctioningAgent(), ConservativeAgent()],
        scenario=get_scenario("liquidation-cascade"),
        max_ticks=ticks,
        recorder=ReplayRecorder(log_dir=str(tmp_path)),
    )
    return engine.run()


def test_run_completes_with_malfunctioning_agent(tmp_path):
    result = _run(tmp_path)

    assert isinstance(result, SimulationResult)
    data = result.to_dict()
    assert len(data["agents"]) == 2
    assert len(data["reliability_reports"]) == 2
    assert data["ticks"] == 16


def test_malfunctioning_agent_accumulates_integrity_events(tmp_path):
    result = _run(tmp_path)
    reports = {r["agent_id"]: r for r in result.to_dict()["agent_reports"]}

    chaos = reports["agent-chaos-001"]
    baseline = reports["agent-conservative-001"]

    # Every chaos tick tripped the boundary; the clean baseline never did.
    assert chaos["decision_integrity_events"] > 0
    assert baseline["decision_integrity_events"] == 0


def test_executed_actions_stay_within_safe_bounds(tmp_path):
    """Even from garbage input, what reaches the market is always canonical."""
    engine = SimulationEngine(
        agents=[MalfunctioningAgent(), ConservativeAgent()],
        scenario=get_scenario("flash-crash"),
        max_ticks=12,
        recorder=ReplayRecorder(log_dir=str(tmp_path)),
    )
    engine.run()

    for entry in engine.recorder.entries:
        assert entry.executed_action in ALLOWED_ACTIONS
        size = entry.metadata.get("size")
        assert isinstance(size, float) and math.isfinite(size)
        assert 0.0 <= size <= MAX_SIZE
