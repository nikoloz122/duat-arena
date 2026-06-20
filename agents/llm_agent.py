"""A real LLM-powered trading agent that rides the existing decision boundary.

This builds ONE autonomous AI agent as a `CallableAgentAdapter`, so it flows
through the engine's `DecisionNormalizer` exactly like any other agent. The
adapter never validates the model's output — the boundary does — so authentic
LLM failure modes (hallucinated actions, malformed JSON, timeouts) are measured
as `decision_integrity` loss rather than papered over.

Cost-safety and determinism: every per-tick response is recorded to a local
cache keyed by the actual decision inputs. A live run calls the API once and
records; replays/demos read from the cache and make zero API calls, so they are
free and fully deterministic. With no key and no cache, the agent degrades to
safe holds and the run still completes.

Secrets: the API key is read from the environment (ANTHROPIC_API_KEY), loaded
from a gitignored .env if present. Keys are never hardcoded or committed.
"""

import hashlib
import json
import logging
import os
import socket
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable, Mapping, Optional

logger = logging.getLogger(__name__)

from agents.adapters import CallableAgentAdapter
from agents.base import TradingAgent
from simulation.market import MarketState

PROJECT_ROOT = Path(__file__).resolve().parent.parent

LLM_AGENT_ID = "agent-llm-momentum-001"
LLM_AGENT_NAME = "LLM Momentum Trader"

MODE_AUTO = "auto"
MODE_REPLAY = "replay"

DEFAULT_MODEL = "claude-3-5-haiku-latest"
DEFAULT_TIMEOUT_SECONDS = 20.0
DEFAULT_MAX_TOKENS = 256
DEFAULT_CACHE_PATH = str(PROJECT_ROOT / "logs" / "llm_cache.json")

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"

SYSTEM_PROMPT = (
    "You are an aggressive momentum on-chain trading agent in a stress-test arena. "
    "Each tick you receive market and portfolio state and must act. "
    'Respond with ONLY a JSON object and nothing else: '
    '{"action": one of "buy"|"sell"|"hold"|"reduce_exposure", '
    '"size": number, "reason": short string, "confidence": number between 0 and 1}.'
)

# A transport: (model, system, user, timeout) -> raw assistant text. May raise;
# the agent absorbs any failure into a safe hold.
LlmClient = Callable[[str, str, str, float], str]

LOG_PREVIEW_CHARS = 500


def _preview(text: Optional[str], limit: int = LOG_PREVIEW_CHARS) -> str:
    """Return a log-safe snippet of model text (never includes secrets)."""
    if text is None:
        return "<none>"
    if text == "":
        return "<empty>"
    if len(text) <= limit:
        return text
    return f"{text[:limit]}... ({len(text)} chars total)"


def _load_dotenv() -> None:
    """Load KEY=VALUE pairs from the project .env into os.environ (no override).

    Minimal and dependency-free. Existing environment variables win, so real
    deployment config is never clobbered by the file.
    """
    env_path = PROJECT_ROOT / ".env"
    if not env_path.exists():
        return
    try:
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value
    except OSError:
        # A missing/unreadable .env must never break agent construction.
        return


_load_dotenv()


def llm_runtime_status() -> dict[str, Any]:
    """Non-secret snapshot of LLM agent configuration for ops / health checks."""
    cache_path = Path(os.getenv("DUAT_LLM_CACHE") or DEFAULT_CACHE_PATH)
    cache_entries = 0
    if cache_path.exists():
        try:
            data = json.loads(cache_path.read_text(encoding="utf-8")) or {}
            cache_entries = len(data) if isinstance(data, dict) else 0
        except (OSError, json.JSONDecodeError):
            cache_entries = 0
    mode = (os.getenv("DUAT_LLM_MODE") or MODE_AUTO).lower()
    return {
        "mode": mode,
        "model": os.getenv("DUAT_LLM_MODEL") or DEFAULT_MODEL,
        "cache_path": str(cache_path),
        "cache_exists": cache_path.exists(),
        "cache_entries": cache_entries,
        "api_key_configured": bool((os.getenv("ANTHROPIC_API_KEY") or "").strip()),
    }


class ResponseCache:
    """A tiny JSON-file cache of raw model responses keyed by decision inputs."""

    def __init__(self, path: str) -> None:
        self.path = Path(path)
        self._data: dict[str, str] = {}
        if self.path.exists():
            try:
                self._data = json.loads(self.path.read_text(encoding="utf-8")) or {}
            except (OSError, json.JSONDecodeError):
                self._data = {}

    def get(self, key: str) -> Optional[str]:
        return self._data.get(key)

    def put(self, key: str, value: str) -> None:
        self._data[key] = value
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(
                json.dumps(self._data, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except OSError:
            # Failing to persist the cache must not break the run.
            pass


def _make_key(agent_id: str, tick: int, market_state: MarketState, snapshot: Optional[dict]) -> str:
    """Deterministic cache key from the actual decision inputs.

    Hashing the market/portfolio state inherently distinguishes scenarios
    (their state sequences differ), so replays are reproducible without
    threading a scenario id through the agent contract.
    """
    payload = json.dumps(
        {"tick": tick, "market": market_state.to_dict(), "portfolio": snapshot},
        sort_keys=True,
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
    return f"{agent_id}:{tick}:{digest}"


def _user_prompt(tick: int, market_state: MarketState, snapshot: Optional[dict]) -> str:
    market = market_state.to_dict()
    parts = [
        f"Tick {tick}.",
        (
            f"Market: price={market.get('current_price')}, "
            f"liquidity={market.get('liquidity')}, "
            f"volatility={market.get('volatility')}, "
            f"sentiment={market.get('market_sentiment')}."
        ),
    ]
    if snapshot:
        parts.append(
            f"Your portfolio: cash={snapshot.get('cash')}, "
            f"position={snapshot.get('position')}, equity={snapshot.get('equity')}, "
            f"exposure={snapshot.get('exposure')}, status={snapshot.get('status')}."
        )
    parts.append("Decide now. Respond with ONLY the JSON object.")
    return " ".join(parts)


def _loads_object(candidate: str) -> Optional[dict]:
    """json.loads `candidate`, returning it only if it is a JSON object."""
    try:
        obj = json.loads(candidate)
    except (json.JSONDecodeError, TypeError):
        return None
    return obj if isinstance(obj, dict) else None


def _first_json_object(text: str) -> Optional[str]:
    """Return the first balanced ``{...}`` block in `text`, or None.

    String-aware so braces inside string values do not break the balance. This
    extracts the JSON real models emit inside Markdown fences or prose.
    """
    start = text.find("{")
    if start == -1:
        return None

    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    return None


def _parse_decision(text: Optional[str]) -> Optional[dict]:
    """Parse model text into a decision dict, or None if no JSON object is found.

    Real models often wrap valid JSON in Markdown fences (```json ... ```) or a
    sentence of prose. We first try the clean string, then fall back to the
    first balanced ``{...}`` block. Parsing only extracts what the model
    actually returned; the DecisionNormalizer still validates every field, so
    hallucinated actions and bad values are still caught downstream. Genuinely
    unusable output (no JSON object) returns None -> safe hold + integrity loss.
    """
    if not text:
        return None

    direct = _loads_object(text.strip())
    if direct is not None:
        return direct

    block = _first_json_object(text)
    if block is not None:
        return _loads_object(block)
    return None


def _anthropic_request(
    model: str, system: str, user: str, timeout: float, api_key: str, max_tokens: int
) -> str:
    body = {
        "model": model,
        "max_tokens": max_tokens,
        "system": system,
        "messages": [{"role": "user", "content": user}],
    }
    request = urllib.request.Request(
        ANTHROPIC_API_URL,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "x-api-key": api_key,
            "anthropic-version": ANTHROPIC_VERSION,
            "content-type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        data = json.loads(response.read().decode("utf-8"))
    blocks = data.get("content", []) or []
    return "".join(b.get("text", "") for b in blocks if b.get("type") == "text")


def build_llm_agent(
    agent_id: str = LLM_AGENT_ID,
    name: str = LLM_AGENT_NAME,
    *,
    model: Optional[str] = None,
    mode: Optional[str] = None,
    cache_path: Optional[str] = None,
    client: Optional[LlmClient] = None,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> TradingAgent:
    """Build the LLM agent as an external CallableAgentAdapter.

    Construction does no network and needs no key, so it is safe to register and
    list. The API is only ever called at decide-time on a cache miss in auto
    mode with a key present.
    """
    model = model or os.getenv("DUAT_LLM_MODEL") or DEFAULT_MODEL
    mode = (mode or os.getenv("DUAT_LLM_MODE") or MODE_AUTO).lower()
    cache = ResponseCache(cache_path or os.getenv("DUAT_LLM_CACHE") or DEFAULT_CACHE_PATH)

    def _log_no_decision(reason: str, tick: int, *, cache_key: str, **details: Any) -> None:
        detail_parts = " ".join(f"{key}={value!r}" for key, value in details.items())
        logger.warning(
            "llm no decision: %s agent=%s tick=%d cache_key=%s %s",
            reason,
            agent_id,
            tick,
            cache_key,
            detail_parts,
        )

    def decide(tick: int, market_state: MarketState, portfolio_snapshot: Any = None) -> Any:
        snapshot = dict(portfolio_snapshot) if isinstance(portfolio_snapshot, Mapping) else None
        key = _make_key(agent_id, tick, market_state, snapshot)

        cached = cache.get(key)
        if cached is not None:
            parsed = _parse_decision(cached)
            if parsed is None:
                _log_no_decision(
                    "cache_parser_failure",
                    tick,
                    cache_key=key,
                    raw_response=_preview(cached),
                )
            return parsed

        if mode == MODE_REPLAY:
            _log_no_decision("replay_cache_miss", tick, cache_key=key, mode=mode)
            return None

        system = SYSTEM_PROMPT
        user = _user_prompt(tick, market_state, snapshot)

        try:
            if client is not None:
                logger.info(
                    "llm API request started agent=%s tick=%d model=%s cache_key=%s "
                    "timeout=%.1fs transport=injectable_client",
                    agent_id,
                    tick,
                    model,
                    key,
                    timeout,
                )
                text = client(model, system, user, timeout)
            else:
                api_key = (os.getenv("ANTHROPIC_API_KEY") or "").strip()
                if not api_key:
                    _log_no_decision("missing_api_key", tick, cache_key=key, mode=mode)
                    return None
                logger.info(
                    "llm API request started agent=%s tick=%d model=%s cache_key=%s "
                    "timeout=%.1fs transport=anthropic_http",
                    agent_id,
                    tick,
                    model,
                    key,
                    timeout,
                )
                text = _anthropic_request(model, system, user, timeout, api_key, max_tokens)
        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            _log_no_decision(
                "http_error",
                tick,
                cache_key=key,
                status=exc.code,
                reason=exc.reason,
                error_body=_preview(error_body),
            )
            return None
        except (TimeoutError, socket.timeout) as exc:
            _log_no_decision(
                "timeout_error",
                tick,
                cache_key=key,
                timeout_seconds=timeout,
                error=f"{type(exc).__name__}: {exc}",
            )
            return None
        except urllib.error.URLError as exc:
            _log_no_decision(
                "network_error",
                tick,
                cache_key=key,
                error=f"{type(exc).__name__}: {exc.reason}",
            )
            return None
        except json.JSONDecodeError as exc:
            _log_no_decision(
                "api_response_json_decode_error",
                tick,
                cache_key=key,
                error=f"{type(exc).__name__}: {exc}",
            )
            return None
        except Exception as exc:  # noqa: BLE001 - any client/transport failure -> safe hold
            _log_no_decision(
                "unexpected_error",
                tick,
                cache_key=key,
                error=f"{type(exc).__name__}: {exc}",
            )
            return None

        logger.info(
            "llm API response received agent=%s tick=%d cache_key=%s length=%d raw=%s",
            agent_id,
            tick,
            key,
            len(text or ""),
            _preview(text),
        )

        if text is None:
            _log_no_decision("empty_response", tick, cache_key=key, raw_response="<none>")
            return None
        if text == "":
            _log_no_decision("empty_response", tick, cache_key=key, raw_response="<empty>")
            return None

        cache.put(key, text)
        parsed = _parse_decision(text)
        if parsed is None:
            _log_no_decision(
                "parser_failure",
                tick,
                cache_key=key,
                raw_response=_preview(text),
            )
        return parsed

    return CallableAgentAdapter(agent_id, decide, name=name, risk_profile="llm")
