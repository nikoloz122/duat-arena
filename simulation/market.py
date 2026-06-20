from dataclasses import asdict, dataclass
from typing import Dict


@dataclass
class MarketState:
    """
    Represents the current state of the simulated market.
    All values are mutable and updated during simulation ticks.
    """
    current_price: float = 100.0
    liquidity: float = 1000.0
    volatility: float = 0.05
    market_sentiment: float = 0.0
    total_volume: float = 0.0          # Added for more realistic market dynamics

    def to_dict(self) -> Dict[str, float]:
        """Convert market state to dictionary for logging/replay."""
        return asdict(self)

    def advance_tick(self) -> None:
        """Natural market evolution between agent actions."""
        # Natural price drift based on sentiment and volatility
        drift = (self.market_sentiment * 0.85) - (self.volatility * 1.8)
        
        self.current_price = max(1.0, round(self.current_price + drift, 2))
        
        # Liquidity slowly decays over time
        self.liquidity = max(50.0, round(self.liquidity * 0.992, 2))
        
        # Volatility mean-reverts slowly
        self.volatility = max(0.01, round(self.volatility * 0.965, 4))
        
        # Sentiment slowly fades
        self.market_sentiment = round(self.market_sentiment * 0.93, 4)

    def apply_agent_action(self, action: str, size: float = 1.0) -> None:
        """
        Apply the impact of an agent's action to the market state.
        
        Args:
            action: 'buy', 'sell', 'reduce_exposure', 'hold'
            size: Relative impact size (1.0 = normal, 2.0 = large trade, etc.)
        """
        impact = size * 1.0

        if action == "buy":
            self.current_price = round(self.current_price + impact * 0.65, 2)
            self.liquidity = max(50.0, round(self.liquidity - impact * 9.5, 2))
            self.market_sentiment = min(1.0, round(self.market_sentiment + impact * 0.028, 4))
            self.total_volume += impact * 15

        elif action == "sell":
            self.current_price = max(1.0, round(self.current_price - impact * 0.95, 2))
            self.liquidity = max(50.0, round(self.liquidity - impact * 13.0, 2))
            self.market_sentiment = max(-1.0, round(self.market_sentiment - impact * 0.045, 4))
            self.total_volume += impact * 18

        elif action == "reduce_exposure":
            self.current_price = max(1.0, round(self.current_price - impact * 0.45, 2))
            self.liquidity = max(50.0, round(self.liquidity - impact * 7.0, 2))
            self.market_sentiment = max(-1.0, round(self.market_sentiment - impact * 0.022, 4))
            self.total_volume += impact * 8

        # Keep the MVP deterministic: no random or process-dependent noise.