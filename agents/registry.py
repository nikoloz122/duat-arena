"""In-memory registry for selecting agents by id.

Registration is the only new concept introduced for external agents. The engine
contract is unchanged: the registry simply builds `TradingAgent` instances that
the engine already knows how to run through its decision boundary.

User-registered BYOA agents are persisted in ``BYOAgentStore`` and synced into
this registry on startup and on every CRUD operation.
"""

from typing import Any, Callable, Dict, List, Optional, Tuple

from agents.base import TradingAgent
from agents.byoa_store import BYOAgentRecord, BYOAgentStore, get_byoa_store
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
    def __init__(self, store: Optional[BYOAgentStore] = None) -> None:
        self._factories: Dict[str, Tuple[AgentFactory, str]] = {}
        self._remote_meta: Dict[str, BYOAgentRecord] = {}
        self._store = store

    def attach_store(self, store: BYOAgentStore) -> None:
        self._store = store

    def register(self, agent_id: str, factory: AgentFactory, kind: str = EXTERNAL) -> None:
        if not agent_id:
            raise AgentRegistryError("agent_id must be a non-empty string")
        if agent_id in self._factories:
            raise AgentRegistryError(f"Agent id '{agent_id}' is already registered")
        self._factories[agent_id] = (factory, kind)

    def unregister(self, agent_id: str) -> bool:
        removed = agent_id in self._factories
        self._factories.pop(agent_id, None)
        self._remote_meta.pop(agent_id, None)
        return removed

    def register_remote(
        self,
        agent_id: str,
        endpoint: str,
        name: Optional[str] = None,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        auth_type: str = "none",
        auth_secret: Optional[str] = None,
        post_fn: Optional[PostFn] = None,
        record: Optional[BYOAgentRecord] = None,
    ) -> None:
        """Register a remote HTTP agent server-side.

        Endpoints are configured here, never accepted from a run request, so the
        API exposes no arbitrary-URL (SSRF) surface during simulation runs.
        """
        if not endpoint:
            raise AgentRegistryError("endpoint must be a non-empty URL")

        if record is not None:
            self._remote_meta[agent_id] = record

        def factory() -> TradingAgent:
            return RemoteHttpAgentAdapter(
                agent_id=agent_id,
                endpoint=endpoint,
                name=name,
                timeout=timeout,
                auth_type=auth_type,
                auth_secret=auth_secret,
                post_fn=post_fn,
            )

        if agent_id in self._factories:
            self._factories[agent_id] = (factory, REMOTE)
        else:
            self.register(agent_id, factory, kind=REMOTE)

    def sync_from_store(self) -> None:
        """Load enabled BYOA agents from the local store into the registry."""
        if self._store is None:
            return
        for record in self._store.list():
            if not record.enabled:
                self.unregister(record.id)
                continue
            secret = self._store.decrypted_secret(record.id)
            self.register_remote(
                record.id,
                record.endpoint,
                name=record.name,
                timeout=record.timeout,
                auth_type=record.auth_type,
                auth_secret=secret,
                record=record,
            )

    def is_registered(self, agent_id: str) -> bool:
        return agent_id in self._factories

    def is_remote(self, agent_id: str) -> bool:
        _, kind = self._factories.get(agent_id, (None, ""))
        return kind == REMOTE

    def ids(self) -> List[str]:
        return list(self._factories.keys())

    def list_agents(self) -> List[Dict[str, Any]]:
        """Return id, name, kind, and BYOA metadata for every registered agent."""
        listing: List[Dict[str, Any]] = []
        listed_ids: set[str] = set()

        for agent_id, (factory, kind) in self._factories.items():
            agent = factory()
            item: Dict[str, Any] = {
                "id": agent_id,
                "name": agent.name,
                "kind": kind,
            }
            if kind == REMOTE:
                item.update(self._remote_listing_fields(agent_id, agent))
            listing.append(item)
            listed_ids.add(agent_id)

        # Disabled BYOA agents stay in the store but are not registered for runs.
        if self._store is not None:
            for record in self._store.list():
                if record.id in listed_ids:
                    continue
                listing.append(
                    {
                        "id": record.id,
                        "name": record.name,
                        "kind": REMOTE,
                        **self._remote_listing_fields(record.id, None, record=record),
                    }
                )
        return listing

    def _remote_listing_fields(
        self,
        agent_id: str,
        agent: Optional[TradingAgent] = None,
        record: Optional[BYOAgentRecord] = None,
    ) -> Dict[str, Any]:
        record = record or self._remote_meta.get(agent_id)
        if record is not None:
            return {
                "description": record.description,
                "endpoint": record.endpoint,
                "auth_type": record.auth_type,
                "timeout": record.timeout,
                "enabled": record.enabled,
                "connection_status": record.connection_status,
                "last_latency_ms": record.last_latency_ms,
                "last_tested_at": record.last_tested_at,
                "has_secret": bool(record.secret_encrypted),
            }
        if isinstance(agent, RemoteHttpAgentAdapter):
            return {"endpoint": agent.endpoint, "enabled": True}
        return {"enabled": True}

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
            record = self._remote_meta.get(agent_id)
            if record is not None and not record.enabled:
                raise AgentRegistryError(f"Agent '{agent_id}' is disabled")

        return [self._factories[agent_id][0]() for agent_id in agent_ids]


def build_default_registry(store: Optional[BYOAgentStore] = None) -> AgentRegistry:
    """A fresh registry with the three preset agents registered."""
    registry = AgentRegistry(store=store)
    registry.register("agent-conservative-001", ConservativeAgent, kind=PRESET)
    registry.register("agent-momentum-001", MomentumAgent, kind=PRESET)
    registry.register("agent-panic-seller-001", PanicSellerAgent, kind=PRESET)
    return registry


def bootstrap_default_registry(log_dir: str = "logs") -> AgentRegistry:
    """Build the default registry, attach BYOA persistence, and sync remotes."""
    store = get_byoa_store(log_dir)
    registry = build_default_registry(store=store)
    registry.attach_store(store)
    registry.sync_from_store()
    return registry


# Module-level default registry used by the API. External agents can be
# registered onto a fresh registry; this one holds the built-in presets.
DEFAULT_REGISTRY = bootstrap_default_registry()

# Register the real LLM agent on the shared registry only (intentionally NOT in
# build_default_registry, so preset-only callers and tests are unaffected). It
# is built lazily and does no network at construction, so listing it is safe.
from agents.llm_agent import LLM_AGENT_ID, build_llm_agent  # noqa: E402

DEFAULT_REGISTRY.register(LLM_AGENT_ID, build_llm_agent, kind=EXTERNAL)
