# DUAT Arena Roadmap

## Done

- Deterministic simulation and replay loop.
- Decision boundary (`DecisionNormalizer`) that safely absorbs malformed or raising agents.
- PortfolioState, BehaviorTracker, and rule-based FailureAnalysis.
- Explainable DUAT Reliability Score (weighted components, grades, `ScoreConfig`).
- In-process external agents via `AgentRegistry` and `CallableAgentAdapter`, with explicit `agent_kind` identity.
- Remote HTTP agents via `RemoteHttpAgentAdapter` (server-side registered endpoints, single attempt + timeout, transport failures degrade to a safe hold through the same decision boundary).
- Runtime remote agent registration via `POST /api/agents/remote` with SSRF guard (`backend/core/url_guard.py`).
- LLM agent with cost-safe response cache (`agents/llm_agent.py`, `logs/llm_cache.json`).
- Six chaos scenarios behind a single scenario registry (flash-crash, liquidity-drain, panic-contagion, oracle-failure, stablecoin-depeg, liquidation-cascade).
- Self-describing replays: JSONL body + manifest sidecar + run-summary sidecar.
- Run history listing and side-by-side reliability comparison.
- Integrity categorization (`simulation/integrity.py`) and scorecard assembly (`simulation/scorecard.py`).
- Deterministic remediation guidance (`simulation/remediation.py`) — presentational, no scoring impact.
- API views: `GET /api/replays/{id}/integrity`, `GET /api/replays/{id}/scorecards`.
- Next.js dashboard (primary demo UI): scenario/agent selection, run simulation, replay timeline, integrity violations, reliability scorecards, recommended fixes, bring-your-own-agent registration.
- Streamlit dashboard (secondary UI): reliability headline, integrity breakdown, scorecards, agent selection, and run comparison.
- Fuzz and invariant tests for the decision boundary and simulation consistency.
- CI workflow (pytest on push/PR).
- Focused test suite covering the engine, boundary, scoring, scenarios, agents, comparison, remediation, and registration (223 tests).

## Next

- Browse past runs in the Next.js UI (`GET /api/replays` already exists on the backend).
- Surface richer comparison and trends in the dashboard (e.g. same agent across scenarios).
- Per-agent risk configuration and behavior-derived contagion.
- Replay search and filtering as run history grows.

## Later

- Execution isolation / sandboxing for untrusted external and remote agents.
- Outbound auth (API key / bearer token) when calling a remote agent endpoint.
- Retries / backoff for transient remote-agent failures.
- Per-session agent registration isolation (currently in-memory, process-global).
- Persistence beyond local JSONL + sidecars only if it proves necessary.

## Not Yet

- Authentication.
- Databases.
- Production deployment (Render/Vercel or similar).
- Distributed queues.
- Real broker integrations.
- Enterprise observability stacks.
- Hosted API key for public LLM agent runs (cost guard needed first).

The product's edge is answering "why did the agent fail, and how reliable is it under stress" — deterministically, explainably, and replayably.
