"""BYOA agent management routes (register, test, CRUD, docs)."""

from __future__ import annotations

import hashlib
import re
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from agents.byoa_crypto import encrypt_secret
from agents.byoa_http import AUTH_NONE, AUTH_TYPES, probe_decide_endpoint
from agents.byoa_store import BYOAgentRecord, get_byoa_store, _utc_now
from agents.registry import DEFAULT_REGISTRY
from backend.api.byoa_docs import integration_docs_payload
from backend.core.config import settings
from backend.core.rate_limit import SlidingWindowRateLimiter
from backend.core.security import require_arena_api_key
from backend.core.url_guard import validate_public_url

byoa_router = APIRouter(tags=["BYOA Agents"])

_test_rate_limiter = SlidingWindowRateLimiter(
    max_calls=settings.byoa_test_rate_limit,
    window_seconds=settings.byoa_test_rate_window_seconds,
)

_manage_deps = [Depends(require_arena_api_key)]


class RemoteAgentRequest(BaseModel):
    """Register or update a user's own HTTP agent."""
    name: str = Field(..., min_length=1, max_length=80)
    description: str = Field(default="", max_length=500)
    endpoint: str = Field(..., min_length=1)
    auth_type: Literal["none", "api_key", "bearer"] = AUTH_NONE
    secret: Optional[str] = Field(default=None, max_length=512)
    timeout: float = Field(default=5.0, gt=0, le=30)


class RemoteAgentUpdateRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=80)
    description: Optional[str] = Field(default=None, max_length=500)
    endpoint: Optional[str] = Field(default=None, min_length=1)
    auth_type: Optional[Literal["none", "api_key", "bearer"]] = None
    secret: Optional[str] = Field(default=None, max_length=512)
    timeout: Optional[float] = Field(default=None, gt=0, le=30)
    enabled: Optional[bool] = None


class TestConnectionRequest(BaseModel):
    """Probe an endpoint before or after registration."""
    endpoint: str = Field(..., min_length=1)
    auth_type: Literal["none", "api_key", "bearer"] = AUTH_NONE
    secret: Optional[str] = Field(default=None, max_length=512)
    timeout: float = Field(default=5.0, gt=0, le=30)
    agent_id: Optional[str] = None


def _remote_agent_id(name: str, endpoint: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "agent"
    digest = hashlib.sha1(endpoint.encode("utf-8")).hexdigest()[:8]
    return f"agent-remote-{slug}-{digest}"


def _validate_auth(auth_type: str, secret: Optional[str]) -> None:
    if auth_type not in AUTH_TYPES:
        raise HTTPException(status_code=400, detail=f"Invalid auth_type: {auth_type}")
    if auth_type != AUTH_NONE and not (secret or "").strip():
        raise HTTPException(
            status_code=400,
            detail=f"Secret is required when auth_type is '{auth_type}'",
        )


def _resolve_secret(
    auth_type: str,
    secret: Optional[str],
    agent_id: Optional[str] = None,
) -> str:
    if secret is not None and secret.strip():
        return secret.strip()
    if agent_id:
        store = get_byoa_store(settings.replay_log_dir)
        return store.decrypted_secret(agent_id)
    return ""


def _apply_record_to_registry(record: BYOAgentRecord) -> None:
    store = get_byoa_store(settings.replay_log_dir)
    if not record.enabled:
        DEFAULT_REGISTRY.unregister(record.id)
        return
    secret = store.decrypted_secret(record.id)
    DEFAULT_REGISTRY.register_remote(
        record.id,
        record.endpoint,
        name=record.name,
        timeout=record.timeout,
        auth_type=record.auth_type,
        auth_secret=secret,
        record=record,
    )


def _public_record(record: BYOAgentRecord) -> dict:
    return record.to_public_dict()


@byoa_router.get("/byoa/docs")
async def get_byoa_docs():
    """Integration guide: OpenAPI spec and starter templates."""
    return integration_docs_payload()


@byoa_router.get("/byoa/openapi.json")
async def get_byoa_openapi():
    return integration_docs_payload()["openapi"]


@byoa_router.post("/agents/remote/test", dependencies=_manage_deps)
async def test_remote_agent(request: TestConnectionRequest, http_request: Request):
    """Probe a remote decide endpoint and validate the BYOA contract."""
    client_host = http_request.client.host if http_request.client else "unknown"
    _test_rate_limiter.check(client_host)

    try:
        safe_url = validate_public_url(request.endpoint)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    _validate_auth(request.auth_type, _resolve_secret(request.auth_type, request.secret, request.agent_id))

    secret = _resolve_secret(request.auth_type, request.secret, request.agent_id)
    result = probe_decide_endpoint(
        url=safe_url,
        timeout=request.timeout,
        auth_type=request.auth_type,
        secret=secret,
    )

    if request.agent_id:
        store = get_byoa_store(settings.replay_log_dir)
        record = store.get(request.agent_id)
        if record is not None:
            record.connection_status = result.connection_status
            record.last_latency_ms = result.latency_ms
            record.last_tested_at = _utc_now()
            store.upsert(record)

    return {
        "success": result.success,
        "status_code": result.status_code,
        "latency_ms": round(result.latency_ms, 2) if result.latency_ms is not None else None,
        "connection_status": result.connection_status,
        "errors": result.errors,
        "sample_response": result.body if result.success else None,
    }


@byoa_router.post("/agents/remote", dependencies=_manage_deps)
async def register_remote_agent(request: RemoteAgentRequest):
    """Register a user-provided HTTP agent (persisted locally)."""
    try:
        safe_url = validate_public_url(request.endpoint)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    _validate_auth(request.auth_type, request.secret)

    store = get_byoa_store(settings.replay_log_dir)
    agent_id = _remote_agent_id(request.name, safe_url)
    existing = store.get(agent_id)

    record = BYOAgentRecord(
        id=agent_id,
        name=request.name.strip(),
        description=request.description.strip(),
        endpoint=safe_url,
        auth_type=request.auth_type,
        secret_encrypted=existing.secret_encrypted if existing else "",
        timeout=request.timeout,
        enabled=True if existing is None else existing.enabled,
        connection_status=existing.connection_status if existing else "offline",
        last_latency_ms=existing.last_latency_ms if existing else None,
        last_tested_at=existing.last_tested_at if existing else None,
        created_at=existing.created_at if existing else _utc_now(),
    )
    if request.secret is not None and request.secret.strip():
        record.secret_encrypted = encrypt_secret(request.secret.strip())

    store.upsert(record)
    _apply_record_to_registry(record)
    return _public_record(record)


@byoa_router.get("/agents/remote/{agent_id}", dependencies=_manage_deps)
async def get_remote_agent(agent_id: str):
    store = get_byoa_store(settings.replay_log_dir)
    record = store.get(agent_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")
    return _public_record(record)


@byoa_router.put("/agents/remote/{agent_id}", dependencies=_manage_deps)
async def update_remote_agent(agent_id: str, request: RemoteAgentUpdateRequest):
    store = get_byoa_store(settings.replay_log_dir)
    record = store.get(agent_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")

    if request.name is not None:
        record.name = request.name.strip()
    if request.description is not None:
        record.description = request.description.strip()
    if request.endpoint is not None:
        try:
            record.endpoint = validate_public_url(request.endpoint)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    if request.auth_type is not None:
        record.auth_type = request.auth_type
    if request.timeout is not None:
        record.timeout = request.timeout
    if request.enabled is not None:
        record.enabled = request.enabled

    auth_type = record.auth_type
    if request.secret is not None and request.secret.strip():
        store.set_secret(agent_id, request.secret.strip())
        record = store.get(agent_id) or record
    elif auth_type != AUTH_NONE:
        _validate_auth(auth_type, store.decrypted_secret(agent_id))

    store.upsert(record)
    _apply_record_to_registry(record)
    return _public_record(record)


@byoa_router.delete("/agents/remote/{agent_id}", dependencies=_manage_deps)
async def delete_remote_agent(agent_id: str):
    store = get_byoa_store(settings.replay_log_dir)
    if not store.delete(agent_id):
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")
    DEFAULT_REGISTRY.unregister(agent_id)
    return {"deleted": True, "id": agent_id}


@byoa_router.post("/agents/remote/{agent_id}/enable", dependencies=_manage_deps)
async def enable_remote_agent(agent_id: str):
    return await update_remote_agent(agent_id, RemoteAgentUpdateRequest(enabled=True))


@byoa_router.post("/agents/remote/{agent_id}/disable", dependencies=_manage_deps)
async def disable_remote_agent(agent_id: str):
    return await update_remote_agent(agent_id, RemoteAgentUpdateRequest(enabled=False))


@byoa_router.post("/agents/remote/{agent_id}/retest", dependencies=_manage_deps)
async def retest_remote_agent(agent_id: str, http_request: Request):
    client_host = http_request.client.host if http_request.client else "unknown"
    _test_rate_limiter.check(client_host)

    store = get_byoa_store(settings.replay_log_dir)
    record = store.get(agent_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")

    secret = store.decrypted_secret(agent_id)
    return await test_remote_agent(
        TestConnectionRequest(
            endpoint=record.endpoint,
            auth_type=record.auth_type,  # type: ignore[arg-type]
            secret=secret or None,
            timeout=record.timeout,
            agent_id=agent_id,
        )
    )
