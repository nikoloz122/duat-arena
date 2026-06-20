import hashlib
import re
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from agents.llm_agent import llm_runtime_status
from agents.registry import DEFAULT_REGISTRY, REMOTE, AgentRegistryError
from agents.templates import build_default_agents
from backend.core.config import settings
from backend.core.url_guard import validate_public_url
from scenarios.registry import get_scenario, list_scenarios as registry_list_scenarios
from simulation.engine import SimulationEngine
from simulation.integrity import categorize_events
from simulation.replay import ReplayRecorder
from simulation.replay_parser import (
    ReplayNotFoundError,
    list_runs,
    load_replay,
    load_run_summary,
)
from simulation.scorecard import build_scorecards

router = APIRouter(tags=["Simulation"])


class SimulationRunRequest(BaseModel):
    """Request model for running a simulation."""
    scenario_id: str = Field(default="flash-crash", description="ID of the chaos scenario")
    ticks: int = Field(default=30, ge=5, le=200, description="Number of ticks to simulate")
    agent_count: int = Field(default=3, ge=1, le=20)
    agent_ids: Optional[List[str]] = Field(
        default=None,
        description="Explicit registered agent ids to run. Falls back to presets when omitted.",
    )


class ReplayCompareRequest(BaseModel):
    """Request model for comparing reliability across runs."""
    replay_ids: List[str] = Field(..., min_length=2, description="Replay ids to compare")


class RemoteAgentRequest(BaseModel):
    """Request to register a user's own agent reachable over HTTP."""
    name: str = Field(..., min_length=1, max_length=80, description="Display name")
    endpoint: str = Field(..., min_length=1, description="HTTP(S) decision endpoint URL")
    timeout: float = Field(default=5.0, gt=0, le=30, description="Per-call timeout (s)")


def _remote_agent_id(name: str, endpoint: str) -> str:
    """Derive a stable, server-controlled id from name + endpoint.

    The endpoint is hashed so the same name+endpoint always maps to the same id
    (enabling idempotent registration), while the client can never choose or
    spoof an id.
    """
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "agent"
    digest = hashlib.sha1(endpoint.encode("utf-8")).hexdigest()[:8]
    return f"agent-remote-{slug}-{digest}"


@router.get("/health")
async def health():
    """Public health check with LLM deployment diagnostics (no secrets)."""
    llm = llm_runtime_status()
    mode = llm["mode"]
    api_key_configured = llm["api_key_configured"]
    cache_entries = llm["cache_entries"]
    return {
        "status": "ok",
        "service": "duat-arena",
        "DUAT_LLM_MODE": mode,
        "model": llm["model"],
        "api_key_configured": api_key_configured,
        "cache_entries": cache_entries,
        "llm_ready": cache_entries > 0 or (mode == "auto" and api_key_configured),
    }


@router.get("/scenarios")
async def list_scenarios():
    """Return available chaos scenarios."""
    return registry_list_scenarios()


@router.get("/agents")
async def list_agents():
    """Return registered agents (presets and any registered external agents)."""
    return DEFAULT_REGISTRY.list_agents()


@router.post("/agents/remote")
async def register_remote_agent(request: RemoteAgentRequest):
    """Register a user-provided HTTP agent so it can be selected for a run.

    The endpoint is SSRF-guarded before registration. The id is derived
    server-side from name+endpoint, so re-registering the same agent is
    idempotent rather than an error. Registration is in-memory/per-process.
    """
    try:
        safe_url = validate_public_url(request.endpoint)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    agent_id = _remote_agent_id(request.name, safe_url)

    # Same name+endpoint -> same id: return it idempotently.
    if DEFAULT_REGISTRY.is_registered(agent_id):
        return {"id": agent_id, "name": request.name, "kind": REMOTE}

    try:
        DEFAULT_REGISTRY.register_remote(
            agent_id, safe_url, name=request.name, timeout=request.timeout
        )
    except AgentRegistryError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {"id": agent_id, "name": request.name, "kind": REMOTE}


@router.post("/simulations/run")
async def run_simulation(request: SimulationRunRequest):
    """Run a chaos simulation with selected parameters."""
    # Select scenario from the single registry (unknown ids fall back to default).
    scenario = get_scenario(request.scenario_id)

    # Explicit agent selection takes precedence; otherwise fall back to the
    # preset slice for backward compatibility.
    if request.agent_ids:
        try:
            agents = DEFAULT_REGISTRY.build(request.agent_ids)
        except AgentRegistryError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    else:
        preset_agents = build_default_agents()
        if request.agent_count > len(preset_agents):
            raise HTTPException(
                status_code=400,
                detail=f"agent_count must be between 1 and {len(preset_agents)} for the current MVP agents.",
            )
        agents = preset_agents[:request.agent_count]

    engine = SimulationEngine(
        agents=agents,
        scenario=scenario,
        max_ticks=request.ticks,
        recorder=ReplayRecorder(log_dir=settings.replay_log_dir),
    )

    result = engine.run()
    return result.to_dict()


@router.get("/replays")
async def list_replays():
    """List available runs with brief reliability metadata."""
    return list_runs(log_dir=settings.replay_log_dir)


@router.post("/replays/compare")
async def compare_replays(request: ReplayCompareRequest):
    """Compare reliability scores side-by-side across multiple runs."""
    comparison = []
    for replay_id in request.replay_ids:
        summary = load_run_summary(replay_id, log_dir=settings.replay_log_dir)
        if summary is None:
            raise HTTPException(
                status_code=404,
                detail=f"Run summary for replay '{replay_id}' not found.",
            )
        agents = [
            {
                "agent_id": report.get("agent_id"),
                "score": report.get("score"),
                "grade": report.get("grade"),
            }
            for report in summary.get("reliability_reports", []) or []
        ]
        comparison.append(
            {
                "replay_id": replay_id,
                "scenario": summary.get("scenario"),
                "agents": agents,
            }
        )
    return {"runs": comparison}


@router.get("/replays/{replay_id}/integrity")
async def get_replay_integrity(replay_id: str):
    """Categorized decision-boundary interceptions for a run.

    Thin wrapper over `simulation.integrity.categorize_events` applied to the
    replay's real events — no fabricated violations, no new computation.
    """
    try:
        replay = load_replay(replay_id, log_dir=settings.replay_log_dir)
    except ReplayNotFoundError as exc:
        raise HTTPException(
            status_code=404, detail=f"Replay '{replay_id}' not found."
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return categorize_events(replay.get("events", []))


@router.get("/replays/{replay_id}/scorecards")
async def get_replay_scorecards(replay_id: str):
    """Per-agent reliability scorecards for a run.

    Thin wrapper over `simulation.scorecard.build_scorecards`, assembled from
    the run's persisted summary plus its replay events. Requires a summary
    sidecar (legacy replays without one return 404).
    """
    summary = load_run_summary(replay_id, log_dir=settings.replay_log_dir)
    if summary is None:
        raise HTTPException(
            status_code=404,
            detail=f"Run summary for replay '{replay_id}' not found.",
        )
    try:
        replay = load_replay(replay_id, log_dir=settings.replay_log_dir)
    except ReplayNotFoundError as exc:
        raise HTTPException(
            status_code=404, detail=f"Replay '{replay_id}' not found."
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"replay_id": replay_id, "scorecards": build_scorecards(summary, replay.get("events", []))}


@router.get("/replays/{replay_id}")
async def get_replay(replay_id: str):
    """Retrieve a specific replay by ID."""
    try:
        return load_replay(replay_id, log_dir=settings.replay_log_dir)
    except ReplayNotFoundError as exc:
        raise HTTPException(
            status_code=404, 
            detail=f"Replay '{replay_id}' not found."
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=400, 
            detail=str(exc)
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500, 
            detail="Internal server error while loading replay."
        ) from exc