from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any


class EventType(StrEnum):
    MARKET_TICK = "market_tick"
    CHAOS_INJECTION = "chaos_injection"
    AGENT_DECISION = "agent_decision"
    SYSTEM = "system"


@dataclass
class SimulationEvent:
    tick: int
    type: EventType
    source: str
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["type"] = self.type.value
        return data


@dataclass
class ReplayEntry:
    timestamp: str
    tick: int
    agent: str
    action: str
    market_state: dict[str, Any]
    scenario_event: dict[str, Any] | None = None
    reason: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    portfolio_state: dict[str, Any] = field(default_factory=dict)
    behavior_counters: dict[str, Any] = field(default_factory=dict)
    # Phase 1 hardening: audit trail for the decision boundary.
    # `action` stays equal to `executed_action` for backward compatibility.
    intended_action: str = ""
    executed_action: str = ""
    normalization_notes: list[str] = field(default_factory=list)
    # Temporary ops diagnostics for the built-in LLM agent (tick 0 only).
    llm_decide_diagnostics: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        if data.get("llm_decide_diagnostics") is None:
            data.pop("llm_decide_diagnostics", None)
        return data