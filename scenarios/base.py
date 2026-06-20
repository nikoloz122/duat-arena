from abc import ABC, abstractmethod

from simulation.events import SimulationEvent
from simulation.market import MarketState


class ChaosScenario(ABC):
    id: str
    name: str

    @abstractmethod
    def apply(self, tick: int, market_state: MarketState) -> SimulationEvent | None:
        """Mutate market state and return the scenario event for this tick."""
