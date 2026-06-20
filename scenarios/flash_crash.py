from scenarios.base import ChaosScenario
from simulation.events import EventType, SimulationEvent
from simulation.market import MarketState


class FlashCrashScenario(ChaosScenario):
    id = "flash-crash"
    name = "Flash Crash"
    description = "A single sharp price collapse with a liquidity and volatility shock."
    crash_tick = 3

    def apply(self, tick: int, market_state: MarketState) -> SimulationEvent | None:
        if tick != self.crash_tick:
            return None

        market_state.current_price = max(1.0, round(market_state.current_price * 0.68, 2))
        market_state.liquidity = max(0.0, round(market_state.liquidity * 0.42, 2))
        market_state.volatility = round(market_state.volatility + 0.32, 4)
        market_state.market_sentiment = -0.85

        return SimulationEvent(
            tick=tick,
            type=EventType.CHAOS_INJECTION,
            source=self.id,
            payload={
                "shock": "flash_crash",
                "severity": "high",
                "price_multiplier": 0.68,
                "liquidity_multiplier": 0.42,
                "volatility_delta": 0.32,
                "sentiment": -0.85,
            },
        )
