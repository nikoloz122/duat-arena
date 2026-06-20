# DUAT Arena — Jury Notes

**One-line pitch:** DUAT stress-tests autonomous trading bots and AI agents through deterministic DeFi catastrophes and returns an explainable, replayable reliability grade — then lets builders fix agents in Agent Lab and re-test via HTTP.

---

## What We Built

| Capability | Description |
| --- | --- |
| **Stress testing arena** | Six deterministic chaos scenarios (flash crash, liquidity drain, panic contagion, oracle failure, stablecoin depeg, liquidation cascade). |
| **Autonomous agent evaluation** | Agents decide every tick; the engine applies outcomes and records a full replay. |
| **Failure detection** | Portfolio rules mark agents **Failed** (drawdown breach) or **Liquidated** (equity floor) while the run continues for audit. |
| **Integrity validation** | A decision normalizer enforces the action contract; every intervention is logged and scored. |
| **Explainable grading** | Strategy Reliability Score (0–100) with weighted components and plain-language rationale. |
| **Bring Your Own Agent** | Register any remote HTTP decision endpoint; Arena grades it through the same boundary as built-ins. |
| **Agent improvement loop** | Fail in Arena → read scorecard → improve in Agent Lab → register remote agent → re-test. |

---

## Demonstrated Result (Liquidation Cascade, 30 ticks)

| Agent | Score | Grade | Status |
| --- | --- | --- | --- |
| Original built-in LLM Momentum Agent | 59 / 100 | C | Failed |
| Improved Agent Lab LLM Momentum Agent v2 | 99 / 100 | A | Active |

**Delta:** 59 → 99 · C → A · Failed → Active — same scenario, same rules.

![Scorecard evidence — side-by-side reliability grades after Liquidation Cascade](screenshots/05-after-scorecard.png)

*Left panel: Agent Lab v2 (Active). Right panel: built-in LLM (Failed). See [`README_RESULTS.md`](README_RESULTS.md).*

---

## Why Judges Should Care

### 1. Stress testing autonomous agents

Most agent demos show happy-path reasoning. DUAT shows **failure-path behavior** under scripted catastrophes that mirror real DeFi stress — with deterministic replays judges can inspect.

### 2. Failure detection

DUAT separates *simulation completion* from *agent survival*. An agent can finish the run and still be marked **Failed**. That distinction matters for capital allocation decisions.

### 3. Integrity validation

LLM and remote agents are untrusted inputs. DUAT's decision boundary converts malformed or unsafe outputs into logged holds — and penalizes **decision integrity** in the score. This is production-relevant safety engineering, not a toy backtester.

### 4. Agent improvement loop

The demo is not "our bot makes money." It is:

1. Original LLM agent fails grading in Arena.
2. Findings drive changes in Agent Lab.
3. Improved remote agent re-tested in Arena.
4. Reliability moves from **59 to 99**, **C to A**, **Failed to Active**.

That closed loop is the product thesis.

### 5. Bring Your Own Agent

Builders keep code and API keys in their own infrastructure. Arena only POSTs `{ tick, market_state, portfolio_snapshot }` and grades the JSON response. No code upload. No vendor lock-in for agent logic.

### 6. Real remote HTTP agents

The improved agent is not a renamed preset — it is a **live HTTP endpoint** (Agent Lab) registered through Arena's remote-agent API and graded by the same engine as built-in bots.

---

## Architecture Highlights (Technical Credibility)

- **Deterministic simulation** — reproducible scenarios and replay logs; no random noise in the MVP market model.
- **Single decision boundary** — preset, LLM, and remote agents all pass through `DecisionNormalizer`.
- **Observable systems** — score breakdown, integrity notes, recommended fixes, and JSONL replay per run.
- **Local-first MVP** — FastAPI + Next.js, 223 automated tests, CI on push/PR.
- **SSRF guard** on remote registration — Arena rejects loopback/private endpoints; production agents exposed via public URL (e.g. ngrok for demo).

---

## What DUAT Is Not (Scope Discipline)

- Not a trading bot marketplace
- Not a historical CSV backtester
- Not copy trading or social trading
- Not production deployment infrastructure (yet)

DUAT is the **grading arena** — the trust layer comes after the testing loop is proven.

---

## Suggested Judge Questions We Answer Well

| Question | Answer |
| --- | --- |
| "How is this different from backtesting?" | Deterministic **chaos** scenarios targeting failure modes, plus integrity enforcement and survivability grading — not return optimization on historical data. |
| "Can I test my own agent?" | Yes — register an HTTP endpoint; Arena grades decisions through the same pipeline. |
| "How do you handle bad LLM output?" | Decision normalizer + integrity scoring; violations appear in the scorecard and replay. |
| "Show me improvement, not just failure." | Built-in LLM **59 / C / Failed** → Agent Lab v2 **99 / A / Active** on the same cascade. |

---

## Files to Review

| Document | Purpose |
| --- | --- |
| [README_RESULTS.md](README_RESULTS.md) | Full before/after results write-up |
| [DEMO_STORY.md](DEMO_STORY.md) | 2-minute narrative |
| [DEMO_SCRIPT.md](DEMO_SCRIPT.md) | Live demo step-by-step |
| [screenshots/](screenshots/) | UI evidence (capture before submission) |
