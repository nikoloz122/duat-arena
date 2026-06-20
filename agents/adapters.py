"""Adapters that turn user-provided agents into DUAT TradingAgents.

External authors should not need to subclass TradingAgent. `CallableAgentAdapter`
wraps a plain function so it can run in the engine. The adapter intentionally
does NOT validate the function's output: the engine's DecisionNormalizer remains
the single decision boundary, so an external agent that returns junk, NaN, or
an invalid action is handled exactly like any other agent.
"""

import inspect
from typing import Any, Callable, Optional

from agents.base import AgentDecision, TradingAgent
from simulation.market import MarketState

# A user decide function. May return an AgentDecision or a plain dict; may
# optionally accept a read-only portfolio_snapshot.
DecideFn = Callable[..., Any]


class CallableAgentAdapter(TradingAgent):
    """Wrap a plain callable as an external TradingAgent."""

    def __init__(
        self,
        agent_id: str,
        decide_fn: DecideFn,
        name: Optional[str] = None,
        risk_profile: str = "custom",
        is_panic_agent: bool = False,
    ) -> None:
        super().__init__(
            agent_id=agent_id,
            risk_profile=risk_profile,
            name=name,
            agent_kind="external",
        )
        self.is_panic_agent = is_panic_agent
        self._decide_fn = decide_fn
        try:
            params = inspect.signature(decide_fn).parameters
            self._fn_accepts_snapshot = "portfolio_snapshot" in params
        except (TypeError, ValueError):
            self._fn_accepts_snapshot = False

    def decide(
        self, tick: int, market_state: MarketState, portfolio_snapshot: Any = None
    ) -> AgentDecision:
        # Pass through the raw return value. The engine normalizes it; the
        # adapter must not introduce a second validation layer.
        if self._fn_accepts_snapshot:
            return self._decide_fn(
                tick=tick, market_state=market_state, portfolio_snapshot=portfolio_snapshot
            )
        return self._decide_fn(tick=tick, market_state=market_state)
