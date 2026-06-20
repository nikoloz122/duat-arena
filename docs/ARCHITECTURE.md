# DUAT Arena Architecture

DUAT Arena is a local-first reliability-testing platform for autonomous financial agents. It runs agents through deterministic chaos scenarios, records self-describing replays, and produces an explainable reliability score so runs can be inspected and compared.

## Current Shape

- `backend/` exposes the FastAPI app and API routes.
- `simulation/` owns the deterministic engine and its supporting pieces: market state, the decision boundary, portfolio accounting, behavior tracking, failure analysis, reliability scoring, integrity categorization (`integrity.py`), deterministic remediation guidance (`remediation.py`), the run manifest, and replay read/write.
- `agents/` contains the trading agent contract, preset templates, the agent registry, the callable adapter for in-process external agents, the remote HTTP adapter for out-of-process agents, and the LLM agent with response cache.
- `scenarios/` contains chaos scenario implementations and a single scenario registry.
- `frontend/` is the **primary demo UI** (Next.js). It consumes the FastAPI backend via `frontend/lib/api.ts` and renders scenario/agent selection, simulation runs, replay timeline, integrity violations, reliability scorecards, recommended fixes, and bring-your-own-agent registration.
- `dashboard/` is the **secondary UI** (Streamlit). It adds run comparison and is useful for side-by-side reliability review across past runs.
- `logs/` stores local replay JSONL files plus `.manifest.json`, `.summary.json`, and `llm_cache.json` sidecars.

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
5. The engine applies the executed action to the portfolio and the market, records a `ReplayEntry`, and updates behavior counters.
6. After the loop, the engine builds per-agent reports, runs `FailureAnalysis`, and computes a `ReliabilityScore` per agent.
7. `ReplayRecorder` writes the JSONL replay plus a manifest sidecar (scenario, config, agent identities) and a run-summary sidecar (the full result).
8. Read endpoints serve the timeline, integrity categorization, scorecards, run listing, and comparison.

## Bring Your Own Agent

Users can register a remote HTTP agent without modifying server code:

1. User hosts an endpoint that accepts `POST { tick, market_state, portfolio_snapshot }` and returns `{ action, size, reason, confidence }`.
2. User pastes the URL into the Next.js "Bring your own agent" form.
3. `POST /api/agents/remote` validates the URL via `backend/core/url_guard.py` (SSRF guard: rejects loopback, private, link-local, and metadata addresses), generates a server-side `agent_id`, and registers via `AgentRegistry.register_remote`.
4. The new agent appears in `GET /api/agents` and can be selected for a run.
5. Registration is in-memory per process; no persistence.

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
- SSRF guard: `backend/core/url_guard.py`
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

- No database (local JSONL + sidecars only).
- No broker or exchange integrations.
- No distributed queues or workers.
- No auth.
- Remote HTTP agents are supported with SSRF guard on user-supplied URLs, but with no sandboxing/process isolation, no outbound auth to the agent endpoint, and no retries (single attempt with a timeout).
- Remote agent registration is in-memory per process (no persistence, no per-session isolation).
- No production observability stack.
