from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Optional

from simulation.market import MarketState


@dataclass
class AgentDecision:
    """Structured decision returned by an agent."""
    action: str          # "buy", "sell", "reduce_exposure", "hold"
    size: float = 1.0    # Relative size of the action (1.0 = normal)
    reason: str = ""
    confidence: float = 0.5
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action": self.action,
            "size": self.size,
            "reason": self.reason,
            "confidence": self.confidence,
            "metadata": self.metadata or {},
        }


class TradingAgent(ABC):
    """
    Base class for all trading agents in DUAT Arena.
    All custom agents must inherit from this class.
    """

    def __init__(
        self, 
        agent_id: str, 
        risk_profile: str = "moderate",
        name: Optional[str] = None,
        agent_kind: str = "preset",
    ) -> None:
        self.id = agent_id
        self.name = name or agent_id
        self.risk_profile = risk_profile
        self.is_panic_agent = False  # Can be overridden by subclasses
        # Explicit, data-driven identity: "preset" for built-ins, "external"
        # for user-provided/adapter agents. Never derived from the class name.
        self.agent_kind = agent_kind

    @abstractmethod
    def decide(self, tick: int, market_state: MarketState) -> AgentDecision:
        """
        Make a trading decision based on current market state.

        Agents may optionally declare a ``portfolio_snapshot`` keyword parameter
        to receive a read-only view of their own portfolio (cash, position,
        equity, exposure, status) at decision time. The engine passes it only to
        agents that declare it, so preset agents keep this exact signature.

        Returns:
            AgentDecision object containing action, size, reason, etc.
        """
        pass

    def get_info(self) -> Dict[str, Any]:
        """Return basic information about the agent."""
        return {
            "id": self.id,
            "name": self.name,
            "risk_profile": self.risk_profile,
            "is_panic_agent": self.is_panic_agent,
            "agent_type": self.__class__.__name__,
            "agent_kind": self.agent_kind,
        }

    def __str__(self) -> str:
        return f"{self.name} ({self.risk_profile})"

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} id={self.id}>"