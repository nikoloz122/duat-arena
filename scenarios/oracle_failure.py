from scenarios.base import ChaosScenario
from simulation.events import EventType, SimulationEvent
from simulation.market import MarketState


class OracleFailureScenario(ChaosScenario):
    """A broken/lagging price oracle: a sharp dislocation, then a partial snap-back."""

    id = "oracle-failure"
    name = "Oracle Failure"
    description = "A price-oracle dislocation that misprices the market, then partially corrects."

    dislocation_tick = 4
    correction_tick = 6

    def apply(self, tick: int, market_state: MarketState) -> SimulationEvent | None:
        if tick == self.dislocation_tick:
            market_state.current_price = max(1.0, round(market_state.current_price * 0.6, 2))
            market_state.volatility = round(market_state.volatility + 0.28, 4)
            market_state.market_sentiment = max(-1.0, round(market_state.market_sentiment - 0.4, 4))

            return SimulationEvent(
                tick=tick,
                type=EventType.CHAOS_INJECTION,
                source=self.id,
                payload={
                    "shock": "oracle_dislocation",
                    "severity": "high",
                    "price_multiplier": 0.6,
                    "volatility_delta": 0.28,
                },
            )

        if tick == self.correction_tick:
            market_state.current_price = round(market_state.current_price * 1.25, 2)
            market_state.volatility = max(0.01, round(market_state.volatility - 0.10, 4))

            return SimulationEvent(
                tick=tick,
                type=EventType.CHAOS_INJECTION,
                source=self.id,
                payload={
                    "shock": "oracle_correction",
                    "severity": "medium",
                    "price_multiplier": 1.25,
                },
            )

        return None
