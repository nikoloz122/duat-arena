# Production Deploy — Vercel (frontend) + Render (backend)

DUAT Arena splits the demo UI and API. Both must ship the **same BYOA release** or the UI will show stale routes (e.g. `/connect` 404) and old inline ngrok registration.

## Root cause of stale Vercel UI

Vercel builds from **Git**. If `frontend/app/connect/`, `frontend/app/docs/`, `AppShell`, and the updated `Dashboard.tsx` are not on the branch Vercel deploys, production keeps the old Agent Lab inline form and `/connect` returns 404.

**Fix:** commit and push all BYOA frontend + backend files, then redeploy Vercel and Render.

## Vercel (Next.js)

| Setting | Value |
|---------|--------|
| Root Directory | `frontend` |
| Framework | Next.js |
| Build Command | `npm run build` (default) |

### Required environment variables

| Variable | Example | Purpose |
|----------|---------|---------|
| `NEXT_PUBLIC_API_BASE_URL` | `https://your-service.onrender.com` | Render FastAPI backend (no trailing slash) |
| `NEXT_PUBLIC_DUAT_ARENA_API_KEY` | same as backend `DUAT_ARENA_API_KEY` | BYOA management routes (private UI only) |

After env changes, trigger a **Redeploy** in Vercel.

### Routes in current frontend

| Path | Page |
|------|------|
| `/` | Arena (sidebar, run simulation) |
| `/connect` | Connect Your Agent |
| `/docs` | API Documentation |

Local check: `cd frontend && npm run build` — must list `/`, `/connect`, `/docs`.

## Render (FastAPI backend)

BYOA agents persist to `logs/byoa_agents.json` under `REPLAY_LOG_DIR`. Render’s default filesystem is **ephemeral** — redeploys wipe registered agents unless you attach a persistent disk.

### Production environment variables

```bash
ENVIRONMENT=production
DUAT_BYOA_KEY=<long random secret>
DUAT_ARENA_API_KEY=<long random secret>
REPLAY_LOG_DIR=/var/data/logs   # with persistent disk mounted at /var/data
```

### Persistent disk (recommended)

1. Render service → **Disks** → mount `/var/data`
2. Set `REPLAY_LOG_DIR=/var/data/logs`
3. Redeploy

Without a disk, registration works until the next deploy, then agents vanish from `GET /api/agents`.

## Post-registration flow

1. Test Connection → Save on `/connect`
2. Frontend stores agent id in `sessionStorage`, navigates to `/`
3. Arena loads `GET /api/agents` and auto-selects the new agent in the sidebar

## Smoke test

1. `https://<vercel-app>/connect` — not 404
2. Header: Arena · Connect Your Agent · API Documentation (no inline ngrok form on `/`)
3. Save agent → Arena sidebar shows it under **Your Agents**
4. Refresh — agent still listed (Render persistent disk configured)
5. Run simulation with that agent
