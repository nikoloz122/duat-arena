# Replay Logs

Simulation replays and related runtime artifacts are written here.

All files in this directory are **local runtime artifacts** and are **git-ignored** (see `.gitignore`). They are safe to delete locally; the engine will create new ones on the next run.

## Artifact types

| File pattern | Purpose | Created by |
| --- | --- | --- |
| `<run_id>.jsonl` | Per-tick event timeline (the stable, auditable core) | `ReplayRecorder` on every simulation run |
| `<run_id>.manifest.json` | Self-describing run metadata: scenario, config, agent identities (`agent_kind`, `endpoint` for remote agents) | `ReplayRecorder` |
| `<run_id>.summary.json` | Full simulation result including reliability reports, agent reports, and failure analysis | `ReplayRecorder` |
| `llm_cache.json` | Raw LLM responses keyed by decision inputs for cost-safe deterministic replay | `agents/llm_agent.py` on cache miss |

## JSONL event fields

Each line in a `.jsonl` replay is a recorded event:

- `timestamp`
- `tick`
- `agent`
- `action`
- `market_state`
- `scenario_event`
- `reason`
- `metadata`
- `portfolio_state`
- `behavior_counters`
- `intended_action`
- `executed_action`
- `normalization_notes`

## Demo seeding

To populate run history for the Streamlit comparison view or to have replays ready before a demo:

```bash
python scripts/seed_demo.py
```

For a recorded LLM-vs-baseline demo run:

```bash
python scripts/record_llm_demo.py
```

Both scripts write into this directory. Safe to re-run; neither deletes existing logs.

## Git ignore

The following patterns are excluded from version control:

```
logs/*.jsonl
logs/*.manifest.json
logs/*.summary.json
logs/llm_cache*.json
```

If you need to share a demo replay with a reviewer, copy the three sidecar files (`.jsonl`, `.manifest.json`, `.summary.json`) for a specific run id manually.
