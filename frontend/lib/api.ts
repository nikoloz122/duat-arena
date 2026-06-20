// Thin typed client for the DUAT Arena FastAPI backend. No external deps —
// just fetch. Base URL is configurable so the same build can point at a
// non-local backend; it defaults to the local dev server.

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") || "http://localhost:8000";

export interface Scenario {
  id: string;
  name: string;
  description?: string;
}

export interface Agent {
  id: string;
  name: string;
  kind?: string;
}

export interface ReliabilityReport {
  agent_id: string;
  score: number;
  grade: string;
  components: Record<string, number>;
  weighted_components: Record<string, number>;
  rationale: string[];
}

export interface AgentReport {
  agent_id: string;
  status: string;
  equity: number;
  initial_cash: number;
  max_drawdown: number;
  realized_pnl: number;
}

export interface SimulationResult {
  replay_id: string;
  scenario: string;
  ticks: number;
  agents: string[];
  surviving_agents: string[];
  agent_reports: AgentReport[];
  reliability_reports: ReliabilityReport[];
}

export interface ReplayEvent {
  tick: number;
  agent: string;
  action: string;
  reason: string;
  intended_action: string;
  executed_action: string;
  normalization_notes: string[];
  scenario_event: Record<string, unknown> | null;
  market_state: Record<string, unknown>;
  portfolio_state: Record<string, unknown>;
}

export interface Replay {
  replay_id: string;
  total_events: number;
  events: ReplayEvent[];
}

export interface IntegrityCategory {
  key: string;
  label: string;
  severity: string;
  count: number;
}

export interface IntegrityTimelineEntry {
  tick: number;
  agent: string;
  category: string;
  label: string;
  severity: string;
  note: string;
}

export interface IntegrityReport {
  total: number;
  intervention_ticks: number;
  by_category: Record<string, number>;
  by_agent: Record<string, number>;
  categories: IntegrityCategory[];
  timeline: IntegrityTimelineEntry[];
}

export interface RemediationItem {
  issue: string;
  suggested_fix: string;
  reason: string;
}

export interface Scorecard {
  agent_id: string;
  status: string;
  score: number;
  grade: string;
  categories: Record<string, number>;
  category_order: string[];
  category_labels: Record<string, string>;
  explanation: string[];
  integrity: {
    total: number;
    intervention_ticks: number;
    by_category: Record<string, number>;
    categories: IntegrityCategory[];
  };
  recommended_fixes: RemediationItem[];
}

export interface ScorecardsResponse {
  replay_id: string;
  scorecards: Scorecard[];
}

export interface RunRequest {
  scenario_id: string;
  ticks: number;
  agent_ids?: string[];
}

export interface RemoteAgentRequest {
  name: string;
  endpoint: string;
  timeout?: number;
}

async function getJSON<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    throw new Error(await errorDetail(response));
  }
  return (await response.json()) as T;
}

async function postJSON<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    throw new Error(await errorDetail(response));
  }
  return (await response.json()) as T;
}

async function errorDetail(response: Response): Promise<string> {
  try {
    const body = await response.json();
    if (body && typeof body.detail === "string") {
      return `${response.status}: ${body.detail}`;
    }
  } catch {
    // Fall through to the status text below.
  }
  return `${response.status} ${response.statusText}`;
}

export const api = {
  listScenarios: () => getJSON<Scenario[]>("/api/scenarios"),
  listAgents: () => getJSON<Agent[]>("/api/agents"),
  registerRemoteAgent: (body: RemoteAgentRequest) =>
    postJSON<Agent>("/api/agents/remote", body),
  runSimulation: (body: RunRequest) =>
    postJSON<SimulationResult>("/api/simulations/run", body),
  getReplay: (replayId: string) =>
    getJSON<Replay>(`/api/replays/${encodeURIComponent(replayId)}`),
  getIntegrity: (replayId: string) =>
    getJSON<IntegrityReport>(`/api/replays/${encodeURIComponent(replayId)}/integrity`),
  getScorecards: (replayId: string) =>
    getJSON<ScorecardsResponse>(`/api/replays/${encodeURIComponent(replayId)}/scorecards`),
};
