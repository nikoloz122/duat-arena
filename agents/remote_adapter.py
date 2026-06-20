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

import json
import urllib.error
import urllib.request
from typing import Any, Callable, Mapping, Optional

from agents.base import TradingAgent
from simulation.market import MarketState

REMOTE = "remote"

DEFAULT_TIMEOUT_SECONDS = 5.0

# A transport: given (url, json_payload, timeout) it returns the parsed JSON
# response object. It may raise on any failure; the adapter absorbs that.
PostFn = Callable[[str, dict, float], Any]


def _default_post(url: str, payload: dict, timeout: float) -> Any:
    """POST ``payload`` as JSON and return the parsed JSON response.

    Raises on non-2xx status, connection/timeout errors, or non-JSON bodies;
    the adapter catches all of these and falls back to a safe hold.
    """
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    # urlopen raises HTTPError for non-2xx and URLError/TimeoutError otherwise.
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = response.read().decode("utf-8")
    return json.loads(body)


class RemoteHttpAgentAdapter(TradingAgent):
    """Wrap an HTTP endpoint as a remote TradingAgent."""

    def __init__(
        self,
        agent_id: str,
        endpoint: str,
        name: Optional[str] = None,
        risk_profile: str = "remote",
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
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
        # Injectable transport keeps the adapter testable without real network.
        self._post_fn: PostFn = post_fn if post_fn is not None else _default_post

    def decide(
        self, tick: int, market_state: MarketState, portfolio_snapshot: Any = None
    ) -> Any:
        payload = {
            "tick": tick,
            "market_state": market_state.to_dict(),
            "portfolio_snapshot": self._snapshot_to_jsonable(portfolio_snapshot),
        }
        try:
            # Single attempt for MVP: no retries, no streaming, no auth.
            return self._post_fn(self.endpoint, payload, self.timeout)
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
