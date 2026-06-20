"""Self-describing metadata for a simulation run.

A manifest captures everything needed to interpret a replay without access to
the original Python objects: scenario, config, and agent identities. It is
persisted as a sidecar JSON file next to the replay so the JSONL event body
stays byte-for-byte backward compatible.
"""

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

SCHEMA_VERSION = "1.0"
ENGINE_VERSION = "0.1.0"


@dataclass
class AgentIdentity:
    """Stable identity snapshot for one agent, taken at run start."""

    id: str
    name: str
    risk_profile: str
    is_panic_agent: bool
    agent_type: str
    agent_kind: str = "preset"
    # Only set for remote agents; kept out of the dict otherwise so preset and
    # external manifest entries stay byte-for-byte unchanged.
    endpoint: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        if data.get("endpoint") is None:
            data.pop("endpoint")
        return data


@dataclass
class SimulationManifest:
    scenario_id: str
    scenario_name: str
    ticks: int
    simulation_config: Dict[str, Any]
    agents: List[Dict[str, Any]] = field(default_factory=list)
    schema_version: str = SCHEMA_VERSION
    engine_version: str = ENGINE_VERSION

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
