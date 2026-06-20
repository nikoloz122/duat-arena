# DUAT Arena Dashboard

A minimal Streamlit dashboard for running simulations and inspecting replays through the existing backend API.

## Prerequisites

Start the backend first:

```bash
uvicorn backend.main:app --reload --port 8000
```

## Run

From the project root:

```bash
pip install -r dashboard/requirements.txt
streamlit run dashboard/app.py
```

## Configuration

Set the backend base URL if it is not the default:

```bash
set DUAT_API_BASE_URL=http://localhost:8000
```

The default is `http://localhost:8000`.

## Features

- Scenario selector
- Tick count input
- Run Simulation button
- Summary metrics
- Replay timeline
- Agent actions table
