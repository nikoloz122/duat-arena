# DUAT Arena — 2-Minute Demo Story

**Audience:** Hackathon judges · **Duration:** ~2 minutes · **Hero scenario:** Liquidation Cascade, 30 ticks

---

## 1. Problem

Autonomous trading bots and LLM agents deploy into DeFi with real capital — but most teams only backtest on calm markets. When liquidation cascades hit, agents fail in ways backtests never showed: bad JSON, panic buying, ignored drawdown limits, no audit trail.

**The question is not "what was the PnL." It is "does this agent survive chaos — and can you prove it?"**

---

## 2. DUAT Arena

DUAT Arena stress-tests trading bots and AI agents through **deterministic DeFi catastrophes** and returns an explainable **Strategy Reliability Score** with a **fully replayable** decision log.

DUAT does not sell bots. It **grades** them.

---

## 3. Failure Detection

We run the **built-in LLM Momentum Agent** against a **Liquidation Cascade** — three waves of forced selling, liquidity collapse, reflexive drawdowns.

| Metric | Value |
| --- | --- |
| Reliability Score | 59 / 100 |
| Grade | C |
| Status | Failed |

DUAT's scorecard shows *why*: drawdown failure and decision-integrity loss.

---

## 4. Agent Lab Improvements

The agent moves to **DUAT Agent Lab** — survival-first policy, valid JSON, bounded sizing, portfolio guardrails — exposed as a **remote HTTP endpoint**. Arena registers it via **Bring Your Own Agent**.

---

## 5. Re-Test

Same scenario. Same ticks. Same rules. **LLM Momentum Agent v2** from Agent Lab.

---

## 6. Results

![Strategy Reliability Scorecards — v2 (99, A, Active) vs built-in LLM (59, C, Failed)](screenshots/05-after-scorecard.png)

| | Before | After |
| --- | --- | --- |
| Reliability Score | 59 / 100 | **99 / 100** |
| Grade | C | **A** |
| Status | Failed | **Active** |

**Stress → grade → fix → re-grade.**

---

## 7. Why This Matters

Before capital flows to autonomous agents, someone must answer: Does it survive failure modes? Does it violate its decision contract under pressure? Can you replay every tick?

DUAT provides that evidence — for presets, LLM agents, and **any remote HTTP agent**.

---

## Closing line

> "We ran an LLM through a liquidation cascade — it failed at fifty-nine, Grade C. We fixed it in Agent Lab, re-tested the same scenario, and it scored ninety-nine, Grade A, Active. DUAT grades survival; Agent Lab builds toward it."
