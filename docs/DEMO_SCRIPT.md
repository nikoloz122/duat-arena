# DUAT Arena — 2-Minute Cinematic Demo Script

**Audience:** YZi Labs judges  
**Language:** English (spoken lines)  
**Primary UI:** Next.js at `http://localhost:3000`  
**Setup:** Backend on `:8000`, LLM cache populated (`logs/llm_cache.json`)

**Hero run (recorded):** `liquidation-cascade-30t-20260614-152428-400768`  
**Expected live result (cache):** LLM **Grade C (61.71)** vs Conservative **Grade A (96.18)**, **2** integrity interventions

**Backup narrative run:** `stablecoin-depeg-30t-20260614-135253-668851` — UST/LUNA-style depeg, LLM **Grade C (64.53)**, **8** integrity interventions

---

## Pre-demo checklist (30 sec before you start)

- [ ] `python scripts/verify_demo.py` passes (LLM cache + backend health)
- [ ] **One** `npm run dev` on port **3000** (not 3001)
- [ ] `http://localhost:3000` loads; scenarios and agents visible
- [ ] Defaults on load: **Liquidation Cascade**, **Conservative Rule-Based Bot** + **LLM Momentum Agent**, ticks **30**
- [ ] Browser zoom ~100%; dark theme readable on screen share
- [ ] Hide `.env`, terminal noise, unrelated tabs

**Launch commands:**

```powershell
# Terminal 1
uvicorn backend.main:app --reload --port 8000

# Terminal 2
cd frontend && npm run dev
```

If cache is missing, run once before the demo:

```bash
python scripts/record_llm_demo.py --scenario liquidation-cascade --ticks 30
```

---

## Act 1 — Positioning (0:00 – 0:15)

**Screen:** Dashboard hero — *"Stress Testing for Trading Bots & AI Agents."*

**Say:**

> "This is DUAT Arena — not a trading bot seller, not a backtester. It's a stress-testing arena for trading bots and AI agents. Before capital is allocated, DUAT runs them through deterministic DeFi catastrophes and returns an explainable strategy reliability grade — backed by a fully replayable audit trail."

**Do:** Nothing. Let the headline sit for 2 seconds.

---

## Act 2 — The setup (0:15 – 0:35)

**Screen:** Controls — scenario dropdown, agent chips, Run button.

**Say:**

> "We're running a real Claude-powered trading agent against a deterministic conservative baseline — same catastrophe, same market, same rules. The scenario is a Liquidation Cascade: forced selling, liquidity collapse, reflexive drawdowns — the failure modes that actually break on-chain capital."

**Do:**

1. Point at **Liquidation Cascade** (already selected).
2. Point at **LLM Momentum Agent** and **Conservative Rule-Based Bot** checkboxes.
3. Optional glance at "Bring your own agent" — don't expand unless asked.

**Say (optional, 5 sec):**

> "Any builder can plug in their own agent over HTTP — their model, their key. DUAT only grades the decisions."

---

## Act 3 — Launch (0:35 – 0:50)

**Screen:** Click **Run Simulation**. Loading state appears.

**Say:**

> "Thirty ticks. Autonomous decisions. No human in the loop."

**Do:** Click **Run Simulation**. Wait for results (~1–2 sec with cache).

---

## Act 4 — The WOW moment: Integrity (0:50 – 1:15)

**Screen:** **Integrity Violations** panel (first result section after run).

**Say:**

> "Here's what makes DUAT different. The agent is real — it can return malformed output, bad sizes, invalid actions. DUAT's decision boundary intercepts every unsafe decision before it reaches the market."

**Point at the red banner:**

> "DUAT intercepted **two** unsafe AI decisions during this Liquidation Cascade. Each one was normalized to a safe action — the run never crashed."

**Point at the timeline table:**

> "Every interception is recorded per tick. This is auditable AI — not a black box."

**Emotional beat:** DUAT doesn't trust the agent. DUAT measures what happens when the agent misbehaves under stress.

---

## Act 5 — The verdict: Scorecards (1:15 – 1:40)

**Screen:** **Strategy Reliability Scorecards**.

**Say:**

> "Can this AI agent be trusted with capital? Here's the grade."

**Point at LLM card:**

> "LLM Momentum Trader: **Grade C**, sixty-two out of one hundred. Status: **failed** — drawdown exceeded the failure threshold. Real losses under stress."

**Point at Conservative card:**

> "Conservative baseline: **Grade A**, ninety-six out of one hundred. **Active** — survived the same cascade."

**Point at category bars (briefly):**

> "Survival, drawdown control, decision integrity — decomposed, weighted, explainable. Like a credit score for autonomous agents."

**Contrast line:**

> "Same catastrophe. Same infrastructure. Completely different reliability."

---

## Act 6 — Developer guidance (1:40 – 1:52)

**Screen:** Under LLM scorecard — **Recommended Fixes**.

**Say:**

> "DUAT doesn't auto-repair agents. It gives deterministic, developer-oriented guidance — what failed, what to fix, and why. No LLM guessing. Fully replay-safe."

**Point at fixes on screen (hero run):**

> "Output normalization — validate against the decision schema. Drawdown failure — de-risk earlier. Actionable, not decorative."

---

## Act 7 — Replay & close (1:52 – 2:00)

**Screen:** **Replay Timeline** — rows with `intercepted` or `chaos` flags.

**Say:**

> "Every tick is on disk — JSONL replay, manifest, summary sidecar. Same inputs, same outputs, every time. This is CI for on-chain agents: stress, grade, replay, compare."

**Final line:**

> "DUAT Arena answers one question: *under a DeFi catastrophe, how reliable is this agent — and can you prove it?* Thank you."

**Do:** Stop. Don't scroll further.

---

## Timing card

| Time | Beat | Key visual |
|------|------|------------|
| 0:00 | Positioning | Hero headline |
| 0:15 | Setup | Scenario + agents |
| 0:35 | Run | Loading → results |
| 0:50 | **WOW** | Integrity banner: **2 intercepted** |
| 1:15 | Verdict | **C vs A** scorecards |
| 1:40 | Fixes | Recommended Fixes (LLM) |
| 1:52 | Close | Replay timeline + final line |

---

## Backup scenario (if judge asks for another catastrophe)

Switch to **Stablecoin Depeg (UST/LUNA-style)** and run (cache may apply if previously recorded).

Pre-recorded backup in logs: **8** boundary interceptions, LLM **Grade C**.

**Say:**

> "Same agent, UST/LUNA-style depeg spiral — eight boundary interceptions. The grade drops further. The evidence is on the replay."

---

## What NOT to say

- "AI trading simulator"
- "Guaranteed profits" / "beats the market"
- "We fixed the agent automatically"
- Long stack explanations (FastAPI, Next.js) unless asked

---

## Georgian cheat sheet (presenter)

| English | ქართული |
|---------|---------|
| Reliability infrastructure | საიმედოობის ინფრასტრუქტურა |
| Decision boundary | გადაწყვეტილების უსაფრთხო საზღვარი |
| Intercepted unsafe decisions | არასანდო გადაწყვეტილებები დაიჭირა |
| Grade C vs Grade A | LLM-ს C, baseline-ს A |
| Replayable / auditable | ყოველ tick-ს შეგიძლია გადაამოწმო |
| CI for on-chain agents | CI ავტონომიური on-chain აგენტებისთვის |
