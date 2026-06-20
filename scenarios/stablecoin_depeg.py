from scenarios.base import ChaosScenario
from simulation.events import EventType, SimulationEvent
from simulation.market import MarketState


class StablecoinDepegScenario(ChaosScenario):
    """A UST/LUNA-style depeg spiral. Narrative/display only — mechanics unchanged:
    accelerating price decay, collapsing sentiment, draining liquidity.
    """

    id = "stablecoin-depeg"
    name = "Stablecoin Depeg (UST/LUNA-style)"
    description = (
        "A reflexive stablecoin depeg inspired by the UST/LUNA collapse: a breaking "
        "peg triggers panic selling, evaporating liquidity, and accelerating drawdowns "
        "that cascade into autonomous-agent failures."
    )

    depeg_start = 3
    depeg_end = 8

    def apply(self, tick: int, market_state: MarketState) -> SimulationEvent | None:
        if tick < self.depeg_start or tick > self.depeg_end:
            return None

        # depth grows each tick within the window, so the damage accelerates.
        depth = tick - self.depeg_start + 1

        market_state.current_price = max(1.0, round(market_state.current_price * (1.0 - 0.04 * depth), 2))
        market_state.market_sentiment = max(-1.0, round(market_state.market_sentiment - 0.05 * depth, 4))
        market_state.liquidity = max(50.0, round(market_state.liquidity * (1.0 - 0.03 * depth), 2))
        market_state.volatility = round(market_state.volatility + 0.02 * depth, 4)

        if tick == self.depeg_start:
            shock, severity = "depeg_onset", "rising"
        else:
            shock, severity = "depeg_deepening", "high"

        return SimulationEvent(
            tick=tick,
            type=EventType.CHAOS_INJECTION,
            source=self.id,
            payload={"shock": shock, "severity": severity, "depth": depth},
        )
