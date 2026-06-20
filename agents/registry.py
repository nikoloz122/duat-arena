"""In-memory registry for selecting agents by id.

Registration is the only new concept introduced for external agents. The engine
contract is unchanged: the registry simply builds `TradingAgent` instances that
the engine already knows how to run through its decision boundary.
"""

from typing import Callable, Dict, List, Optional, Tuple

from agents.base import TradingAgent
from agents.remote_adapter import (
    DEFAULT_TIMEOUT_SECONDS,
    PostFn,
    RemoteHttpAgentAdapter,
)
from agents.templates import ConservativeAgent, MomentumAgent, PanicSellerAgent

AgentFactory = Callable[[], TradingAgent]

PRESET = "preset"
EXTERNAL = "external"
REMOTE = "remote"


class AgentRegistryError(ValueError):
    """Raised for duplicate, unknown, or invalid agent registrations/requests."""


class AgentRegistry:
    def __init__(self) -> None:
        self._factories: Dict[str, Tuple[AgentFactory, str]] = {}

    def register(self, agent_id: str, factory: AgentFactory, kind: str = EXTERNAL) -> None:
        if not agent_id:
            raise AgentRegistryError("agent_id must be a non-empty string")
        if agent_id in self._factories:
            raise AgentRegistryError(f"Agent id '{agent_id}' is already registered")
        self._factories[agent_id] = (factory, kind)

    def register_remote(
        self,
        agent_id: str,
        endpoint: str,
        name: Optional[str] = None,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        post_fn: Optional[PostFn] = None,
    ) -> None:
        """Register a remote HTTP agent server-side.

        Endpoints are configured here, never accepted from a run request, so the
        API exposes no arbitrary-URL (SSRF) surface in this phase.
        """
        if not endpoint:
            raise AgentRegistryError("endpoint must be a non-empty URL")

        def factory() -> TradingAgent:
            return RemoteHttpAgentAdapter(
                agent_id=agent_id,
                endpoint=endpoint,
                name=name,
                timeout=timeout,
                post_fn=post_fn,
            )

        self.register(agent_id, factory, kind=REMOTE)

    def is_registered(self, agent_id: str) -> bool:
        return agent_id in self._factories

    def ids(self) -> List[str]:
        return list(self._factories.keys())

    def list_agents(self) -> List[Dict[str, str]]:
        """Return id, name, and kind for every registered agent."""
        listing: List[Dict[str, str]] = []
        for agent_id, (factory, kind) in self._factories.items():
            agent = factory()
            listing.append({"id": agent_id, "name": agent.name, "kind": kind})
        return listing

    def build(self, agent_ids: List[str]) -> List[TradingAgent]:
        """Instantiate the requested agents, validating ids and duplicates."""
        if not agent_ids:
            raise AgentRegistryError("At least one agent_id is required")

        seen: set[str] = set()
        for agent_id in agent_ids:
            if agent_id in seen:
                raise AgentRegistryError(f"Duplicate agent_id requested: '{agent_id}'")
            seen.add(agent_id)
            if agent_id not in self._factories:
                raise AgentRegistryError(f"Unknown agent_id: '{agent_id}'")

        return [self._factories[agent_id][0]() for agent_id in agent_ids]


def build_default_registry() -> AgentRegistry:
    """A fresh registry with the three preset agents registered."""
    registry = AgentRegistry()
    registry.register("agent-conservative-001", ConservativeAgent, kind=PRESET)
    registry.register("agent-momentum-001", MomentumAgent, kind=PRESET)
    registry.register("agent-panic-seller-001", PanicSellerAgent, kind=PRESET)
    return registry


# Module-level default registry used by the API. External agents can be
# registered onto a fresh registry; this one holds the built-in presets.
DEFAULT_REGISTRY = build_default_registry()

# Register the real LLM agent on the shared registry only (intentionally NOT in
# build_default_registry, so preset-only callers and tests are unaffected). It
# is built lazily and does no network at construction, so listing it is safe.
from agents.llm_agent import LLM_AGENT_ID, build_llm_agent  # noqa: E402

DEFAULT_REGISTRY.register(LLM_AGENT_ID, build_llm_agent, kind=EXTERNAL)
