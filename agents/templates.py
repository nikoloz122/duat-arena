from agents.base import AgentDecision, TradingAgent
from simulation.market import MarketState


class ConservativeAgent(TradingAgent):
    """Conservative agent that prioritizes capital preservation."""

    def __init__(self, agent_id: str = "agent-conservative-001"):
        super().__init__(agent_id=agent_id, risk_profile="low")
        self.is_panic_agent = False

    def decide(self, tick: int, market_state: MarketState) -> AgentDecision:
        if market_state.liquidity < 700 or market_state.volatility > 0.20:
            return AgentDecision(
                action="reduce_exposure",
                size=0.6,
                reason="High volatility or low liquidity detected",
                confidence=0.82
            )
        return AgentDecision(
            action="hold",
            size=1.0,
            reason="Market conditions are stable",
            confidence=0.75
        )


class MomentumAgent(TradingAgent):
    """Momentum-based agent that follows market trends."""

    def __init__(self, agent_id: str = "agent-momentum-001"):
        super().__init__(agent_id=agent_id, risk_profile="medium")
        self.is_panic_agent = False

    def decide(self, tick: int, market_state: MarketState) -> AgentDecision:
        if market_state.market_sentiment >= 0.0 and market_state.volatility < 0.22:
            return AgentDecision(
                action="buy",
                size=1.1,
                reason="Stable or positive trend with acceptable volatility",
                confidence=0.68
            )
        elif market_state.market_sentiment < -0.25 or market_state.current_price < 78:
            return AgentDecision(
                action="sell",
                size=0.9,
                reason="Negative sentiment or significant price drop",
                confidence=0.72
            )
        return AgentDecision(
            action="hold",
            size=1.0,
            reason="No strong momentum signal",
            confidence=0.60
        )


class PanicSellerAgent(TradingAgent):
    """Highly reactive agent that sells during stress."""

    def __init__(self, agent_id: str = "agent-panic-seller-001"):
        super().__init__(agent_id=agent_id, risk_profile="high")
        self.is_panic_agent = True

    def decide(self, tick: int, market_state: MarketState) -> AgentDecision:
        if market_state.liquidity < 750 or market_state.volatility > 0.22:
            return AgentDecision(
                action="sell",
                size=1.4,
                reason="Critical liquidity drop or extreme volatility",
                confidence=0.88
            )
        elif market_state.market_sentiment < -0.15:
            return AgentDecision(
                action="reduce_exposure",
                size=0.8,
                reason="Negative market sentiment",
                confidence=0.75
            )
        return AgentDecision(
            action="hold",
            size=1.0,
            reason="Conditions not critical enough to panic",
            confidence=0.55
        )


def build_default_agents() -> list[TradingAgent]:
    """Return a set of default agents for quick testing."""
    return [
        ConservativeAgent("agent-conservative-001"),
        MomentumAgent("agent-momentum-001"),
        PanicSellerAgent("agent-panic-seller-001"),
    ]