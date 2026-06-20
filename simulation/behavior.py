from dataclasses import asdict, dataclass
from typing import Any, Dict


@dataclass
class BehaviorCounters:
    """Aggregate, fact-only action counters for a single agent.

    These are raw counts. They do not classify actions as panic, smart, late,
    or risky. Interpretation belongs to a future analysis layer.
    """

    buy_count: int = 0
    sell_count: int = 0
    hold_count: int = 0
    reduce_exposure_count: int = 0
    exposure_increase_count: int = 0
    exposure_reduction_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class BehaviorTracker:
    """Tracks aggregate behavior counters for one agent.

    Stores counters only. Per-action history lives in the replay log, which is
    the source of truth for the timeline.
    """

    def __init__(self, agent_id: str) -> None:
        self.agent_id = agent_id
        self.counters = BehaviorCounters()

    def record(self, action: str, exposure_before: float, exposure_after: float) -> None:
        if action == "buy":
            self.counters.buy_count += 1
        elif action == "sell":
            self.counters.sell_count += 1
        elif action == "reduce_exposure":
            self.counters.reduce_exposure_count += 1
        elif action == "hold":
            self.counters.hold_count += 1

        if exposure_after > exposure_before:
            self.counters.exposure_increase_count += 1
        elif exposure_after < exposure_before:
            self.counters.exposure_reduction_count += 1

    def to_dict(self) -> Dict[str, Any]:
        return self.counters.to_dict()
