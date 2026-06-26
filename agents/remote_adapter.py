"""Adapter for agents that live OUTSIDE the Python process.

`RemoteHttpAgentAdapter` lets a black-box agent reachable over HTTP be tested in
DUAT. It POSTs the decision context to a configured endpoint and returns the raw
response for the engine's DecisionNormalizer to validate. Like every other
agent, it flows through the existing decision boundary; this adapter adds NO
second validation layer.

Failure handling is deliberately boring: on any transport problem (timeout,
connection error, non-2xx status, unreadable/non-JSON body) the adapter returns
``None`` instead of raising. The engine's normalizer turns ``None`` into a safe
hold and records a boundary note, so a flaky or hostile endpoint is penalized on
``decision_integrity`` exactly like a malformed in-process agent, and the run
continues deterministically.
"""

import urllib.error
from typing import Any, Mapping, Optional

from agents.base import TradingAgent
from agents.byoa_contract import build_decide_payload
from agents.byoa_http import AUTH_NONE, PostFn, build_auth_headers, default_post
from simulation.market import MarketState

REMOTE = "remote"

DEFAULT_TIMEOUT_SECONDS = 5.0


def _default_post(url: str, payload: dict, timeout: float, headers: Mapping[str, str]) -> Any:
    status, body = default_post(url, payload, timeout, headers)
    if status < 200 or status >= 300:
        raise urllib.error.HTTPError(url, status, "Non-2xx response", {}, None)
    return body


class RemoteHttpAgentAdapter(TradingAgent):
    """Wrap an HTTP endpoint as a remote TradingAgent."""

    def __init__(
        self,
        agent_id: str,
        endpoint: str,
        name: Optional[str] = None,
        risk_profile: str = "remote",
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        auth_type: str = AUTH_NONE,
        auth_secret: Optional[str] = None,
        post_fn: Optional[PostFn] = None,
    ) -> None:
        super().__init__(
            agent_id=agent_id,
            risk_profile=risk_profile,
            name=name,
            agent_kind=REMOTE,
        )
        if not endpoint:
            raise ValueError("endpoint must be a non-empty URL")
        self.endpoint = endpoint
        self.timeout = timeout
        self.auth_type = auth_type
        self.auth_secret = auth_secret or ""
        # Injectable transport keeps the adapter testable without real network.
        self._post_fn: PostFn = post_fn if post_fn is not None else _default_post

    def decide(
        self, tick: int, market_state: MarketState, portfolio_snapshot: Any = None
    ) -> Any:
        payload = build_decide_payload(
            tick=tick,
            market=market_state.to_dict(),
            portfolio=self._snapshot_to_jsonable(portfolio_snapshot),
        )
        headers = build_auth_headers(self.auth_type, self.auth_secret)
        try:
            # Single attempt for MVP: no retries, no streaming.
            return self._post_fn(self.endpoint, payload, self.timeout, headers)
        except Exception:  # noqa: BLE001 - any transport failure becomes a safe hold
            # Returning None (not raising) hands control to the engine's
            # normalizer, which records a boundary note and a safe hold.
            return None

    @staticmethod
    def _snapshot_to_jsonable(portfolio_snapshot: Any) -> Optional[dict]:
        if portfolio_snapshot is None:
            return None
        if isinstance(portfolio_snapshot, Mapping):
            return dict(portfolio_snapshot)
        return None
