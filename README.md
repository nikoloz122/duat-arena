# DUAT Arena

**Stress Testing & Reliability Grading for Autonomous AI Agents**

DUAT Arena is a deterministic stress-testing platform that evaluates how trading bots and AI agents behave under real DeFi failure modes — liquidation cascades, flash crashes, oracle failures, liquidity crises, and stablecoin depegs.

We do not sell trading bots.

We answer the question that matters before capital is deployed:

> **Will this agent survive when things go wrong — and can you prove it?**

## Demo Results — Agent Lab Improvement Loop

**Scenario:** Liquidation Cascade · **Ticks:** 30 · **Same engine, same rules, re-tested after fixes**

| Agent                           | Reliability Score | Grade | Status |
| ------------------------------- | ----------------- | ----- | ------ |
| Original LLM Momentum Agent     | 59 / 100          | C     | Failed |
| Agent Lab LLM Momentum Agent v2 | 99 / 100          | A     | Active |

![Strategy Reliability Scorecards](docs/screenshots/05-after-scorecard.png)

DUAT identified reliability and decision-integrity failures in the original LLM Momentum Agent. The agent was improved in Agent Lab and re-tested under the exact same stress scenario.

**Result:** 59 → 99
**Grade:** C → A
**Outcome:** Failed → Active

### DUAT Improvement Loop

**Detect → Fix → Verify**

Full analysis:

* docs/README_RESULTS.md
* docs/JURY_NOTES.md
* docs/DEMO_STORY.md

## What DUAT Does Today

- **Six DeFi catastrophe scenarios** — flash crash, liquidity drain, panic contagion, oracle failure, stablecoin depeg, liquidation cascade.
- **Built-in trading bots** — Conservative (rule-based), Momentum, and Panic Seller presets.
- **LLM agent** — Claude-powered momentum trader with deterministic response cache for demo runs.
- **Custom API bots** — register any HTTP endpoint; DUAT grades decisions through the same safety boundary.
- **Strategy reliability score** — 0–100 score and A–F grade with explainable components and replay evidence.
- **Decision-integrity enforcement** — malformed, invalid, or unsafe outputs are intercepted and recorded.
- **Next.js demo UI** — run simulations, view integrity violations, scorecards, recommended fixes, and replay timeline.
- **223 automated tests** and CI on push/PR.

## What's Planned Next

- Browse past runs in the Next.js UI (backend listing already exists).
- Additional bot strategy templates (e.g. RSI, grid) — not yet implemented.
- Richer cross-scenario comparison and trend views.
- Per-agent risk configuration and replay search as run history grows.

See [`docs/ROADMAP.md`](docs/ROADMAP.md) for full detail.

## What DUAT Is Not

- **Not a trading bot marketplace** — DUAT tests bots; it does not sell or deploy them.
- **Not a historical backtester** — scenarios are deterministic chaos stress tests, not CSV replay.
- **Not copy trading or social trading** — no follower feeds, leaderboards, or payment rails.
- **Not production infrastructure (yet)** — local-first MVP; no auth, database, or hosted deployment.

## Future Vision

DUAT is building toward a **trust layer for autonomous finance**: before capital is allocated to a trading bot or AI agent, allocators, protocols, and builders could rely on a standardized, replayable reliability grade — the way lenders rely on a credit score. That path is incremental, not overnight:

| Phase | Focus |
| --- | --- |
| **Today** | **Stress testing** — deterministic DeFi catastrophes, decision-integrity enforcement, and explainable strategy reliability scores in a local-first MVP. |
| **Next** | **Benchmarking & reliability scores** — side-by-side comparison across scenarios, run history, and repeatable grades that teams can use before deployment. |
| **Future** | **Trust layer for autonomous finance** — a widely recognized standard for verifying that autonomous agents behave reliably under stress before they touch real capital. |

That vision requires proven stress testing, explainable scoring, and auditable evidence first. Today's MVP delivers the testing arena and grading pipeline; broader institutional adoption follows only after the core loop is validated. DUAT does not promise marketplaces, token launches, DAO governance, copy trading, or deployment rails — only the reliability infrastructure those systems would eventually need.

Today DUAT evaluates trading bots and AI agents operating in simulated market environments. Over time, the same reliability and stress-testing framework may be extended to broader categories of autonomous financial agents.

## Future Agent Categories

DUAT currently focuses on **trading bots and AI agents that make market decisions** — agents that buy, sell, hold, or adjust exposure in response to simulated market state. That is the scope of the present MVP and demo.

The same evaluation framework — deterministic stress scenarios, decision-integrity enforcement, explainable reliability scores, and replayable evidence — could eventually be extended to additional autonomous agent categories, such as:

- **AI Market Analysts** — agents that interpret market signals and produce actionable views under stress.
- **AI Research Agents** — agents that synthesize on-chain and market data when conditions turn hostile.
- **Token Discovery Agents** — agents that screen and rank opportunities with financial consequences for bad calls.
- **Portfolio Assistants** — agents that recommend or execute allocation changes across a portfolio.
- **Risk Management Agents** — agents responsible for exposure limits, drawdown response, and capital preservation.
- **Yield Optimization Agents** — agents that chase or defend yield when liquidity and peg stability break down.
- **Arbitrage Agents** — agents that exploit or fail on price dislocations during cascades and depegs.

**These categories are future possibilities, not current features.** DUAT does not implement them today. Extending the framework would require new scenario models, agent contracts, and grading dimensions appropriate to each category — work that follows validation of the core trading-bot and AI-agent stress-testing loop.

## Problem

Autonomous agents are starting to manage real capital on-chain, but there is no standard, trustworthy way to verify how they behave under stress *before* they are deployed. Backtesters measure strategy returns on calm history. LLM eval tools measure answer quality. Neither stress-tests an autonomous agent against the failure modes that actually destroy on-chain capital — depegs, oracle manipulation, liquidation cascades — and neither produces a reproducible, auditable measure of reliability. Worse, agents fail in ways code review cannot catch: they hallucinate invalid actions, return malformed decisions, freeze, or panic precisely when conditions turn hostile.

## Why now

On-chain AI agents are moving from demos to capital allocation. As that happens, the missing layer is verification: capital allocators, protocols, and agent builders need to know an agent's reliability the way lenders need a credit score. The agents exist; the infrastructure to grade them does not yet. DUAT is early to that layer, not late — and the model providers will not build it, because a vertical, deterministic stress-and-grading harness sits above the model, not inside it.

## Solution

DUAT runs any agent — preset, in-process, or remote over HTTP — through deterministic chaos scenarios and measures it:

- **Deterministic stress testing.** Scenarios are scripted, reproducible market catastrophes. The same agent and inputs always produce the same run.
- **Decision-integrity enforcement.** Every agent decision passes through a safe boundary that absorbs malformed, invalid, hallucinated, or raising outputs without breaking the run — and records each intervention.
- **Reliability grading.** Each agent gets a 0–100 score and an A–F grade from explainable, weighted components, with a fact-based rationale.
- **Replayable evidence.** Every run is recorded as a self-describing replay (event log + manifest + summary sidecars), so any grade can be reconstructed and audited from disk.
- **Side-by-side evaluation.** Past runs are listed and compared, so agents can be ranked and regressions caught — CI for agents.

## Why DUAT

- **Reproducible by construction.** Determinism makes every grade auditable and every failure debuggable — the foundation of a rating standard.
- **Built for untrusted agents.** The decision boundary means DUAT can grade a black-box or hostile agent safely; broken behavior becomes a measured signal, not a crash.
- **Explainable, not a black box.** Scores decompose into named components with weights and a rationale — defensible to an institutional reviewer.
- **Crypto-native failure library.** The scenarios are the catastrophes that actually break on-chain capital, not generic noise.

## Competition / differentiation

| Category | What it does | What it misses |
| --- | --- | --- |
| Backtesters (Backtrader, QuantConnect) | Strategy returns on historical data | Not built for autonomous agents; no stress/chaos; no reliability grade or integrity enforcement |
| LLM/agent eval (LangSmith, evals) | Answer/prompt quality | No financial consequences, no portfolio/drawdown, no market-catastrophe stress |
| Risk simulation (TradFi) | Portfolio risk under scenarios | Not for autonomous AI agents; not crypto-native; not reproducible agent grading |
| **DUAT Arena** | **Deterministic DeFi-catastrophe stress testing of autonomous agents, with decision-integrity enforcement and an explainable, replayable reliability grade** | — |

The components individually are not novel; the defensible position is the combination and becoming the standard grade agents are measured against.

## How it works

- `backend/` — FastAPI app and API routes.
- `simulation/` — Deterministic engine, decision boundary (`DecisionNormalizer`), portfolio accounting, behavior tracking, failure analysis, reliability scoring, integrity categorization, deterministic remediation guidance, run manifest, and replay read/write.
- `agents/` — Agent contract, preset templates, the agent registry, the callable adapter for in-process agents, the remote HTTP adapter for out-of-process agents, and the LLM agent with response cache.
- `scenarios/` — DeFi catastrophe scenarios and a single scenario registry.
- `frontend/` — **Primary demo UI** (Next.js): scenario/agent selection, run simulation, replay timeline, integrity violations, reliability scorecards, recommended fixes, and bring-your-own-agent registration. Talks to the backend at `http://localhost:8000` via `frontend/lib/api.ts` (`NEXT_PUBLIC_API_BASE_URL` override supported).
- `dashboard/` — **Secondary UI** (Streamlit): reliability grades, integrity breakdown, scorecards, agent selection, and run comparison. Useful when you want side-by-side run comparison without the Next.js app.
- `logs/` — Local replay JSONL files plus manifest, summary, and LLM cache sidecars.

### Scenarios (DeFi catastrophe library)

Six deterministic stress scenarios, each modeling a canonical on-chain failure mode: `flash-crash`, `liquidity-drain`, `panic-contagion`, `oracle-failure`, `stablecoin-depeg` (a UST/LUNA-style depeg spiral — a breaking peg drives panic selling, liquidity evaporation, and reflexive drawdowns), and `liquidation-cascade`.

### Reliability score

Each agent receives a deterministic 0–100 score and an A–F grade, composed from five weighted components — `survival`, `capital_preservation`, `drawdown_control`, `risk_discipline`, and `decision_integrity`. Weights live in `ScoreConfig`, and every score ships with its component breakdown and a fact-based rationale, so the grade is never a black box.

### Agents

DUAT grades three kinds of agents, all selected through the same `AgentRegistry` and all subject to the same decision boundary:

- **Preset** — built-in templates: Conservative Rule-Based Bot, Momentum Trading Bot, Panic Seller Bot.
- **External (in-process)** — any Python callable wrapped by `CallableAgentAdapter`, including the LLM agent (`agent-llm-momentum-001`).
- **Remote (HTTP)** — an out-of-process, black-box agent reachable over HTTP, wrapped by `RemoteHttpAgentAdapter`. It POSTs the decision context (`tick`, `market_state`, `portfolio_snapshot`) to a configured endpoint and passes the raw response straight to the decision boundary.

Remote agents can be registered two ways:

1. **Server-side** — `registry.register_remote(...)` in Python (for tests and local development).
2. **From the Next.js UI** — `POST /api/agents/remote` with `{ name, endpoint, timeout? }`. The URL is SSRF-guarded (`backend/core/url_guard.py`); registration is in-memory per process. The user's model and API key stay on their side.

A remote call is a single attempt with a timeout. Any transport problem (timeout, connection error, non-2xx status, non-JSON body) degrades to a safe hold and lowers the agent's `decision_integrity` — exactly like a malformed in-process agent — so the run always finishes deterministically.

## Current API

- `GET /api/health` — service health check.
- `GET /api/scenarios` — list available DeFi catastrophe scenarios.
- `GET /api/agents` — list registered agents (preset, external, remote).
- `POST /api/agents/remote` — register a user-provided HTTP agent endpoint (SSRF-guarded).
- `POST /api/simulations/run` — run a deterministic stress test and save a replay. Accepts `scenario_id`, `ticks`, `agent_count`, and optional `agent_ids`.
- `GET /api/replays` — list past runs with brief reliability metadata.
- `GET /api/replays/{replay_id}` — load replay metadata, manifest, run summary, and ordered timeline events.
- `GET /api/replays/{replay_id}/integrity` — categorized decision-boundary interceptions for a run.
- `GET /api/replays/{replay_id}/scorecards` — per-agent reliability scorecards with recommended fixes.
- `POST /api/replays/compare` — compare reliability grades across two or more runs by `replay_ids`.

## Quick Start

**Use exactly two terminals** — backend first, then frontend. Run **only one** `npm run dev` (port 3000). A second instance binds to `:3001` and `localhost:3000` may show a blank or broken page.

### 1. Backend (port 8000) — Terminal 1

```bash
pip install -r requirements.txt
uvicorn backend.main:app --reload --port 8000
```

The API starts at `http://localhost:8000`. Interactive docs at `/docs`.

For a consistent local environment, prefer a project virtual environment:

```bash
python -m venv .venv
.venv\Scripts\activate    # Windows
pip install -r requirements.txt
```

On Windows you can also use `./scripts/run_backend.ps1`.

### 2. Frontend (port 3000) — Terminal 2

```bash
cd frontend
npm install
npm run dev
```

Open **http://localhost:3000** (not 3001). The dashboard pre-selects **Liquidation Cascade**, **Conservative Rule-Based Bot**, and **LLM Momentum Agent** for demo runs.

On Windows: `./scripts/run_frontend.ps1` (refuses to start if port 3000 is already in use).

To point at a non-local backend, set `NEXT_PUBLIC_API_BASE_URL` before starting the frontend.

### 3. Verify demo readiness (before presenting)

```bash
python scripts/verify_demo.py
```

Checks that `logs/llm_cache.json` exists (fast, deterministic LLM demo runs). Warns if the backend is not reachable.

If the cache is missing:

```bash
python scripts/record_llm_demo.py --scenario liquidation-cascade --ticks 30
```

Requires `ANTHROPIC_API_KEY` in `.env` for the first recording only.

### 4. Streamlit dashboard (optional, secondary UI)

The Streamlit dashboard adds a run-comparison view. Start the backend first, then:

```bash
pip install -r dashboard/requirements.txt
streamlit run dashboard/app.py
```

On Windows: `./scripts/run_dashboard.ps1` (sets `DUAT_API_BASE_URL` to the local backend).

## Demo Day Checklist

Complete this list **30 minutes before** a live presentation:

- [ ] **One backend:** `uvicorn backend.main:app --reload --port 8000` running
- [ ] **One frontend:** single `npm run dev` in `frontend/` on **port 3000** (not 3001)
- [ ] **Cache check:** `python scripts/verify_demo.py` passes
- [ ] **Browser:** open `http://localhost:3000`, hard refresh (`Ctrl+Shift+R`)
- [ ] **Defaults visible:** Liquidation Cascade + Conservative Rule-Based Bot + LLM Momentum Agent selected
- [ ] **Dry run:** Run Simulation → integrity banner → scorecards (C vs A) → timeline
- [ ] **Backup video:** 2-minute screen recording ready if live demo fails
- [ ] **Script:** [`docs/DEMO_SCRIPT.md`](docs/DEMO_SCRIPT.md) open for talking points
- [ ] **Hide:** `.env`, extra terminal tabs, unrelated browser tabs

## Troubleshooting

### Blank or white page at localhost:3000

Usually a **stale Next.js cache** or a crashed dev server.

```powershell
# Stop all npm run dev processes (Ctrl+C), then:
cd frontend
Remove-Item -Recurse -Force .next
npm run dev
```

Open `http://localhost:3000` and hard refresh.

### Port conflict (3000 vs 3001)

If the terminal says `Port 3000 is in use, trying 3001 instead`, you already have a frontend running.

1. Stop **all** `npm run dev` processes.
2. Start **one** fresh instance.
3. Use **http://localhost:3000** only.

On Windows, `./scripts/run_frontend.ps1` blocks startup if port 3000 is taken.

### Backend not running / frontend cannot reach API

Symptoms: *"Could not reach the backend"* on the dashboard.

1. Start the backend: `uvicorn backend.main:app --reload --port 8000`
2. Confirm: `http://localhost:8000/api/health` returns `{"status":"ok",...}`
3. Refresh the frontend.

### LLM run takes 60+ seconds

The LLM response cache is missing or stale.

```bash
python scripts/verify_demo.py
python scripts/record_llm_demo.py --scenario liquidation-cascade --ticks 30
```

After caching, runs complete in ~1–2 seconds with zero API calls.

### Multiple dev servers

Never run two `npm run dev` instances. Keep exactly **one uvicorn** and **one npm run dev** for demo day.

## Judge Demo Flow

Use this flow when presenting to YZi Labs or any first-time reviewer. Requires backend + Next.js frontend running (see Quick Start).

**Full cinematic script (screen-by-screen, talking points, timing):** [`docs/DEMO_SCRIPT.md`](docs/DEMO_SCRIPT.md).

1. **Open** `http://localhost:3000`.
2. **Scenario:** `Liquidation Cascade` and **Agents:** Conservative Rule-Based Bot + LLM Momentum Agent are pre-selected on load.
3. **Run Simulation** and wait ~1–2 seconds (with LLM cache) or ~5–10 seconds (first run).
4. **What judges should see (top to bottom):**
   - **Integrity Violations** — headline with large count: *"DUAT intercepted N unsafe AI decision(s) during …"*. Category badges and per-tick timeline. This is the WOW moment.
   - **Strategy Reliability Scorecards** — rule-based baseline (typically A/B) vs LLM agent (typically C/D/F), side-by-side.
   - **Recommended Fixes** — under each scorecard: deterministic developer guidance (Issue / Suggested Fix / Reason).
   - **Replay Timeline** — tick-by-tick decisions with `chaos` and `intercepted` flags.

**Talking points:** DUAT does not sell trading bots — it stress-tests them. The LLM agent trades aggressively and fails under stress; DUAT catches every unsafe decision at the boundary and grades reliability. The rule-based baseline survives because it is deterministic and risk-aware.

### Pre-record a demo run (recommended before a live presentation)

```bash
python scripts/record_llm_demo.py
```

First run: one pass of live Anthropic API calls, responses cached to `logs/llm_cache.json`. Later runs with the same scenario + ticks replay from cache with **zero API calls** — fully deterministic. Requires `ANTHROPIC_API_KEY` in `.env` for the initial recording only.

Seed additional preset-only runs for comparison history:

```bash
python scripts/seed_demo.py
```

Safe to re-run; never deletes existing logs.

## Status

DUAT is a deterministic, local-first MVP. The engine, decision boundary, scoring, scenarios, replay/comparison, API, Next.js dashboard, integrity/scorecard views, BYO agent registration, and deterministic remediation guidance are functional and tested (223 tests, CI on push/PR).

Not yet: production deployment, authentication, per-session agent isolation, browse-past-runs in the Next.js UI, or outbound auth to remote agent endpoints — by design, until the product need proves otherwise.
