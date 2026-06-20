# Scripts

Small local helper scripts. Optional — they support local development and demo setup, not replace the README quick start.

## Launch scripts

| Script | What it does |
| --- | --- |
| `run_backend.ps1` | Start the FastAPI backend with reload on port 8000. |
| `run_frontend.ps1` | Start the Next.js dashboard on port 3000 (blocks if port already in use). |
| `run_dashboard.ps1` | Install dashboard requirements and start the Streamlit UI (secondary UI with run comparison). Sets `DUAT_API_BASE_URL` to the local backend. |
| `verify_demo.py` | Pre-demo check: confirms `logs/llm_cache.json` exists and warns if backend is down. |

Typical demo setup (two terminals):

```powershell
./scripts/run_backend.ps1
./scripts/run_frontend.ps1
```

See the README **Quick Start** and **2-minute judge demo** sections for the full flow.

## Demo scripts

| Script | What it does |
| --- | --- |
| `seed_demo.py` | Generate deterministic demo runs (replay + manifest + summary sidecars) across multiple scenarios with preset agents. Populates run history for the Streamlit comparison view. Safe to re-run; never deletes existing logs. |
| `record_llm_demo.py` | Run the real LLM agent against a `ConservativeAgent` baseline through one DeFi catastrophe scenario and record the run. First invocation performs live Anthropic API calls and caches responses to `logs/llm_cache.json`; later runs with the same scenario + ticks replay from cache with zero API calls. Requires `ANTHROPIC_API_KEY` in `.env` for the initial recording. |

```bash
python scripts/seed_demo.py
python scripts/record_llm_demo.py
python scripts/record_llm_demo.py --scenario stablecoin-depeg --ticks 30
```

Recommended before a live presentation: run `record_llm_demo.py` once to populate the LLM cache, then use the Next.js dashboard for the judge demo (see README **2-minute judge demo**).
