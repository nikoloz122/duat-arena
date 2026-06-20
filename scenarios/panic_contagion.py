from scenarios.base import ChaosScenario
from simulation.events import EventType, SimulationEvent
from simulation.market import MarketState


class PanicContagionScenario(ChaosScenario):
    id = "panic-contagion"
    name = "Panic Contagion"
    description = "A spreading sentiment collapse that compounds volatility over time."

    def apply(self, tick: int, market_state: MarketState) -> SimulationEvent | None:
        if tick < 5:
            return None

        market_state.market_sentiment = max(-1.0, round(market_state.market_sentiment - 0.18, 4))
        market_state.volatility = round(market_state.volatility + 0.05, 4)

        return SimulationEvent(
            tick=tick,
            type=EventType.CHAOS_INJECTION,
            source=self.id,
            payload={"shock": "sentiment_cascade", "severity": "rising"},
        )
