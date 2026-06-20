from scenarios.base import ChaosScenario
from simulation.events import EventType, SimulationEvent
from simulation.market import MarketState


class LiquidityDrainScenario(ChaosScenario):
    id = "liquidity-drain"
    name = "Liquidity Drain"
    description = "Repeated order-book thinning that steadily erodes liquidity."

    def apply(self, tick: int, market_state: MarketState) -> SimulationEvent | None:
        if tick not in {2, 4, 6}:
            return None

        market_state.liquidity = max(0.0, round(market_state.liquidity * 0.78, 2))
        market_state.volatility = round(market_state.volatility + 0.08, 4)

        return SimulationEvent(
            tick=tick,
            type=EventType.CHAOS_INJECTION,
            source=self.id,
            payload={"shock": "order_book_thinning", "severity": "medium"},
        )
