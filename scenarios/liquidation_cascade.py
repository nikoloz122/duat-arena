from scenarios.base import ChaosScenario
from simulation.events import EventType, SimulationEvent
from simulation.market import MarketState


class LiquidationCascadeScenario(ChaosScenario):
    """Forced-selling contagion: compounding waves, each worse than the last."""

    id = "liquidation-cascade"
    name = "Liquidation Cascade"
    description = "Successive forced-liquidation waves with deepening price drops and liquidity evaporation."

    cascade_ticks = (3, 5, 7)

    def apply(self, tick: int, market_state: MarketState) -> SimulationEvent | None:
        if tick not in self.cascade_ticks:
            return None

        wave = self.cascade_ticks.index(tick) + 1  # 1, 2, 3 — each wave is worse.

        market_state.current_price = max(1.0, round(market_state.current_price * (1.0 - 0.10 * wave), 2))
        market_state.liquidity = max(50.0, round(market_state.liquidity * (1.0 - 0.15 * wave), 2))
        market_state.volatility = round(market_state.volatility + 0.10 * wave, 4)
        market_state.market_sentiment = max(-1.0, round(market_state.market_sentiment - 0.10 * wave, 4))

        return SimulationEvent(
            tick=tick,
            type=EventType.CHAOS_INJECTION,
            source=self.id,
            payload={"shock": "liquidation_wave", "severity": "high", "wave": wave},
        )
