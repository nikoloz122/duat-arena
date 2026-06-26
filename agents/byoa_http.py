"""HTTP transport for BYOA remote agents (stdlib-only, injectable for tests)."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable, Dict, Mapping, Optional

from agents.byoa_contract import sample_test_payload, validate_decide_response

PostFn = Callable[[str, dict, float, Mapping[str, str]], Any]

AUTH_NONE = "none"
AUTH_API_KEY = "api_key"
AUTH_BEARER = "bearer"
AUTH_TYPES = frozenset({AUTH_NONE, AUTH_API_KEY, AUTH_BEARER})


@dataclass
class HttpProbeResult:
    success: bool
    status_code: Optional[int]
    latency_ms: Optional[float]
    body: Any
    errors: list[str]
    connection_status: str


def build_auth_headers(auth_type: str, secret: Optional[str]) -> Dict[str, str]:
    if auth_type == AUTH_NONE or not secret:
        return {}
    if auth_type == AUTH_API_KEY:
        return {"X-API-Key": secret}
    if auth_type == AUTH_BEARER:
        return {"Authorization": f"Bearer {secret}"}
    return {}


def default_post(
    url: str,
    payload: dict,
    timeout: float,
    headers: Mapping[str, str],
) -> tuple[int, Any]:
    """POST JSON and return ``(status_code, parsed_body)``. Raises on transport errors."""
    merged_headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        **dict(headers),
    }
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers=merged_headers,
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        status = getattr(response, "status", 200)
        body_text = response.read().decode("utf-8")
    try:
        parsed = json.loads(body_text) if body_text else {}
    except json.JSONDecodeError as exc:
        raise ValueError(f"Response body is not valid JSON: {exc}") from exc
    return status, parsed


def probe_decide_endpoint(
    *,
    url: str,
    timeout: float,
    auth_type: str = AUTH_NONE,
    secret: Optional[str] = None,
    payload: Optional[dict] = None,
    post_fn: Optional[PostFn] = None,
) -> HttpProbeResult:
    """Call a remote decide endpoint and validate the contract."""
    from agents.byoa_contract import classify_connection_status

    transport: PostFn = post_fn if post_fn is not None else default_post
    headers = build_auth_headers(auth_type, secret)
    body_payload = payload if payload is not None else sample_test_payload()
    errors: list[str] = []
    started = time.perf_counter()

    try:
        status_code, body = transport(url, body_payload, timeout, headers)
        latency_ms = (time.perf_counter() - started) * 1000.0

        if status_code < 200 or status_code >= 300:
            errors.append(f"HTTP status {status_code} (expected 2xx)")
            return HttpProbeResult(
                success=False,
                status_code=status_code,
                latency_ms=latency_ms,
                body=body,
                errors=errors,
                connection_status=classify_connection_status(success=False, latency_ms=latency_ms),
            )

        valid, schema_errors = validate_decide_response(body)
        if not valid:
            errors.extend(schema_errors)

        success = valid
        return HttpProbeResult(
            success=success,
            status_code=status_code,
            latency_ms=latency_ms,
            body=body,
            errors=errors,
            connection_status=classify_connection_status(success=success, latency_ms=latency_ms),
        )
    except urllib.error.HTTPError as exc:
        latency_ms = (time.perf_counter() - started) * 1000.0
        errors.append(f"HTTP error {exc.code}: {exc.reason}")
        return HttpProbeResult(
            success=False,
            status_code=exc.code,
            latency_ms=latency_ms,
            body=None,
            errors=errors,
            connection_status="offline",
        )
    except urllib.error.URLError as exc:
        latency_ms = (time.perf_counter() - started) * 1000.0
        errors.append(f"Connection failed: {exc.reason}")
        return HttpProbeResult(
            success=False,
            status_code=None,
            latency_ms=latency_ms,
            body=None,
            errors=errors,
            connection_status="offline",
        )
    except TimeoutError:
        latency_ms = (time.perf_counter() - started) * 1000.0
        errors.append(f"Request timed out after {timeout}s")
        return HttpProbeResult(
            success=False,
            status_code=None,
            latency_ms=latency_ms,
            body=None,
            errors=errors,
            connection_status="offline",
        )
    except ValueError as exc:
        latency_ms = (time.perf_counter() - started) * 1000.0
        errors.append(str(exc))
        return HttpProbeResult(
            success=False,
            status_code=None,
            latency_ms=latency_ms,
            body=None,
            errors=errors,
            connection_status="offline",
        )
    except Exception as exc:  # noqa: BLE001 - probe must never crash callers
        latency_ms = (time.perf_counter() - started) * 1000.0
        errors.append(f"Unexpected error: {exc}")
        return HttpProbeResult(
            success=False,
            status_code=None,
            latency_ms=latency_ms,
            body=None,
            errors=errors,
            connection_status="offline",
        )
