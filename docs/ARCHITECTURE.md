# DUAT Arena Architecture

DUAT Arena is a local-first reliability-testing platform for autonomous financial agents. It runs agents through deterministic chaos scenarios, records self-describing replays, and produces an explainable reliability score so runs can be inspected and compared.

## Current Shape

- `backend/` exposes the FastAPI app and API routes.
- `simulation/` owns the deterministic engine and its supporting pieces: market state, the decision boundary, portfolio accounting, behavior tracking, failure analysis, reliability scoring, integrity categorization (`integrity.py`), deterministic remediation guidance (`remediation.py`), the run manifest, and replay read/write.
- `agents/` contains the trading agent contract, preset templates, the agent registry, the callable adapter for in-process external agents, the remote HTTP adapter for out-of-process agents, and the LLM agent with response cache.
- `scenarios/` contains chaos scenario implementations and a single scenario registry.
- `frontend/` is the **primary demo UI** (Next.js). Pages: **Arena** (`/`), **Connect Your Agent** (`/connect`), **API Documentation** (`/docs`). The UI consumes FastAPI via `frontend/lib/api.ts` and renders scenario/agent selection (sidebar), simulation runs, replay timeline, integrity violations, reliability scorecards, recommended fixes, and BYOA registration.
- `dashboard/` is the **secondary UI** (Streamlit). It adds run comparison and is useful for side-by-side reliability review across past runs.
- `logs/` stores local replay JSONL files plus `.manifest.json`, `.summary.json`, `llm_cache.json`, and `byoa_agents.json` (registered remote agents).

## End-to-End Flow (UI → Grade)

```
Browser (localhost:3000)
  → Next.js Dashboard (frontend/lib/api.ts)
    → FastAPI (backend/api/routes.py)
      → AgentRegistry.build(agent_ids)
      → SimulationEngine.run()
        → per tick: scenario.apply → agent.decide() → DecisionNormalizer → portfolio update → ReplayEntry
      → FailureAnalysis + ReliabilityScore per agent
      → ReplayRecorder → logs/<run_id>.jsonl + .manifest.json + .summary.json
    ← SimulationResult (replay_id)
  → parallel fetch:
      GET /api/replays/{id}           → replay timeline
      GET /api/replays/{id}/integrity → categorized violations
      GET /api/replays/{id}/scorecards → grades + recommended fixes
  → UI panels: Scorecards → Integrity → Timeline
```

## Runtime Flow (Engine)

1. `POST /api/simulations/run` receives a scenario, tick count, and either an `agent_count` (presets) or explicit `agent_ids` (from the agent registry).
2. The engine seeds each agent's portfolio and advances `MarketState` once per tick.
3. The selected scenario can mutate market state for that tick.
4. Each agent's `decide()` output passes through the decision boundary: the `DecisionNormalizer` validates and canonicalizes it, and a raising agent falls back to a safe hold. The original intent and any normalization notes are recorded.
5. Agents run in **request order** within each tick; each executed action mutates the shared `MarketState` before the next agent decides. A multi-agent run on the same scenario is therefore **not comparable** to a solo-agent run with the same tick count.
6. The engine applies the executed action to the portfolio and the market, records a `ReplayEntry`, and updates behavior counters.
7. After the loop, the engine builds per-agent reports, runs `FailureAnalysis`, and computes a `ReliabilityScore` per agent.
8. `ReplayRecorder` writes the JSONL replay plus a manifest sidecar (scenario, config, agent identities) and a run-summary sidecar (the full result).
9. Read endpoints serve the timeline, integrity categorization, scorecards, run listing, and comparison.

## Bring Your Own Agent (BYOA)

DUAT connects **existing** remote agents — it does not build, host, or deploy them. A developer registers an HTTP `POST /decide` endpoint; DUAT validates compatibility, stress-tests under chaos scenarios, and grades reliability.

### UI

| Page | Path | Purpose |
|------|------|---------|
| Connect Your Agent | `/connect` | Name, endpoint URL, optional auth, Test Connection, save/edit/delete/enable/disable |
| API Documentation | `/docs` | Contract, OpenAPI spec, curl/Python/FastAPI/Express examples |
| Arena | `/` | Sidebar lists built-in + connected agents (Online / Slow / Offline); select and run simulation |

### Management API (`backend/api/byoa_routes.py`)

- `POST /api/agents/remote` — register (persisted to `logs/byoa_agents.json`)
- `POST /api/agents/remote/test` — probe endpoint (HTTP status, JSON contract, latency)
- `PUT/DELETE /api/agents/remote/{id}` — edit / remove
- `POST /api/agents/remote/{id}/enable|disable|retest`
- `GET /api/byoa/docs` — integration guide for developers

When `DUAT_ARENA_API_KEY` is set, management routes require header `X-DUAT-Api-Key`. `GET /api/agents` (list for Arena UI) stays open.

### API contract

**Request** (each simulation tick):

```json
{ "tick": 0, "market": { ... }, "portfolio": { ... } }
```

**Response:**

```json
{ "action": "buy|sell|hold|reduce_exposure", "confidence": 0.0-1.0, "size": 0.0-1.0, "reason": "..." }
```

Test Connection **rejects** incompatible responses. During a run, malformed runtime responses are coerced to a safe **hold** by the decision boundary (simulation never crashes).

### BYOA runtime flow (isolated from engine core)

```
User's POST /decide endpoint
  → RemoteHttpAgentAdapter.decide()     (agents/remote_adapter.py)
    → returns raw JSON or None on transport failure
  → SimulationEngine._decide_safely()   (simulation/engine.py)
    → catches exceptions → safe hold
  → DecisionNormalizer                  (simulation/decision_normalizer.py)
    → canonical AgentDecision or safe hold + notes
  → portfolio / market update → ReplayEntry
```

No BYOA imports exist in `simulation/engine.py`. Registry sync loads persisted agents at startup (`agents/registry.py` + `agents/byoa_store.py`).

### Persistence

Registered agents: `logs/byoa_agents.json` (local JSON, replaceable store). Secrets stored encrypted (`agents/byoa_crypto.py`); `DUAT_BYOA_KEY` required when `ENVIRONMENT=production`.

### Security

| Control | Module |
|---------|--------|
| SSRF / URL validation | `backend/core/url_guard.py` |
| Secret encryption | `agents/byoa_crypto.py` |
| Production startup checks | `backend/core/startup.py` |
| Management API key | `backend/core/security.py` |
| Test Connection rate limit | `backend/core/rate_limit.py` |

**Localhost and private IPs are intentionally blocked** for user-supplied agent URLs. The server performs outbound requests to registered endpoints; allowing loopback would be a server-side request forgery (SSRF) risk. Agents running on a developer machine must be exposed via a **public HTTPS URL** (e.g. ngrok, Cloudflare Tunnel) for Test Connection and simulation. This applies in all environments where the SSRF guard is active.

### Production deployment notes

Set before starting the backend (`backend/main.py` calls `validate_production_config()` on import):

```bash
ENVIRONMENT=production
DUAT_BYOA_KEY=<long random secret>
DUAT_ARENA_API_KEY=<long random secret>
```

For a private Next.js UI that calls BYOA management routes, also set `NEXT_PUBLIC_DUAT_ARENA_API_KEY` to the same value as `DUAT_ARENA_API_KEY`. Do not expose that key on an untrusted public browser UI without a backend-for-frontend.

Optional tuning: `DUAT_BYOA_TEST_RATE_LIMIT`, `DUAT_BYOA_TEST_RATE_WINDOW_SECONDS`, `REPLAY_LOG_DIR`.

Server-side `registry.register_remote(...)` remains available for tests and local development.

## Decision Boundary

All agents — preset, in-process external, remote, or LLM — run through the same boundary:

- `simulation/decision_normalizer.py` turns any agent output into a canonical `AgentDecision` (valid action, finite/bounded size, clamped confidence), never raising and producing notes for every change.
- The engine catches exceptions from `decide()` and substitutes a safe hold.
- `RemoteHttpAgentAdapter` is just another `TradingAgent`: it returns the raw HTTP response (or `None` on any transport failure) and the same normalizer validates it. The adapter adds no second validation layer.
- Deviations feed the `decision_integrity` component of the reliability score.

## Integrity & Remediation (Presentational)

- `simulation/integrity.py` categorizes real `normalization_notes` into stable buckets (Malformed Output, Invalid Action, Oversized Position, Timeout, etc.). Pure and deterministic.
- `simulation/scorecard.py` assembles per-agent scorecards from the reliability report, agent report, and integrity timeline. Score and grade pass through unchanged.
- `simulation/remediation.py` maps integrity categories and failure-analysis risk flags to structured developer guidance (`{ issue, suggested_fix, reason }`). **Presentational only** — it does not affect scores, grades, replay content, or simulation results.
- Exposed via `GET /api/replays/{id}/integrity` and `GET /api/replays/{id}/scorecards`.

## Reliability Score

`simulation/scoring.py` computes a deterministic 0-100 score and A-F grade from five weighted components — `survival`, `capital_preservation`, `drawdown_control`, `risk_discipline`, `decision_integrity` — using weights from `ScoreConfig`. Each score carries its component breakdown and a fact-based rationale.

## Source Of Truth

- Agent contract and decision schema: `agents/base.py`
- Agent registry and adapters: `agents/registry.py`, `agents/adapters.py`, `agents/remote_adapter.py`, `agents/llm_agent.py`
- Market state schema: `simulation/market.py`
- Decision boundary: `simulation/decision_normalizer.py`
- Portfolio, behavior, failure analysis: `simulation/portfolio.py`, `simulation/behavior.py`, `simulation/failure_analysis.py`
- Reliability scoring and config: `simulation/scoring.py`, `simulation/config.py`
- Integrity categorization: `simulation/integrity.py`
- Remediation guidance: `simulation/remediation.py`
- Scorecard assembly: `simulation/scorecard.py`
- Scenario event / replay row schemas: `simulation/events.py`
- Run manifest: `simulation/manifest.py`
- Simulation orchestration: `simulation/engine.py`
- Replay write path: `simulation/replay.py`
- Replay read path and run listing/comparison helpers: `simulation/replay_parser.py`
- BYOA management and store: `backend/api/byoa_routes.py`, `agents/byoa_store.py`, `agents/byoa_contract.py`, `agents/byoa_http.py`, `agents/byoa_crypto.py`
- SSRF guard: `backend/core/url_guard.py`
- Production config: `backend/core/config.py`, `backend/core/startup.py`, `backend/core/security.py`, `backend/core/rate_limit.py`
- Scenario implementations and registry: `scenarios/`
- HTTP API surface: `backend/api/routes.py`
- Next.js API client: `frontend/lib/api.ts`

## Replay & Persistence

- The JSONL body is the per-tick event timeline and is the stable, backward-compatible core.
- The `.manifest.json` sidecar makes a replay self-describing (scenario, config, agent identities including `agent_kind`, plus the `endpoint` for remote agents — the field is omitted for non-remote agents).
- The `.summary.json` sidecar persists the full run result (including reliability reports), so a run is reconstructable from disk and comparable to other runs.
- `llm_cache.json` stores raw LLM responses keyed by decision inputs for cost-safe deterministic replay.
- Older replays without sidecars still load; missing sidecars surface as `None`.

## MVP Boundaries

- No database (local JSONL + sidecars + `byoa_agents.json` only).
- No broker or exchange integrations.
- No distributed queues or workers.
- No multi-tenant auth or billing.
- Remote HTTP agents: SSRF guard on user URLs, encrypted secrets, optional API key on BYOA management routes, single HTTP attempt per tick with timeout, no sandboxing of remote code.
- No production observability stack.
