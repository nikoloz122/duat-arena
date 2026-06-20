"use client";

import { useEffect, useState } from "react";

import {
  Agent,
  IntegrityReport,
  Replay,
  Scenario,
  Scorecard,
  SimulationResult,
  API_BASE_URL,
  api,
} from "../../lib/api";
import {
  AGENT_LAB_PRESETS,
  buildAgentLabEndpoint,
  defaultIntegrationConfig,
  fetchAgentLabIntegrationSafe,
  type IntegrationConfig,
} from "../../lib/agentLab";
import {
  AGENT_FILTER_OPTIONS,
  agentLabel,
  agentMatchesFilter,
  agentTypeLabel,
  resolveAgentType,
  type AgentTypeFilter,
} from "../../lib/format";
import IntegrityPanel from "./IntegrityPanel";
import ReplayTimeline from "./ReplayTimeline";
import ScorecardPanel from "./ScorecardPanel";

const DEMO_SCENARIO_ID = "liquidation-cascade";
const DEMO_AGENT_IDS = ["agent-conservative-001", "agent-llm-momentum-001"];

function pickDemoScenario(scenarios: Scenario[]): string {
  return scenarios.find((s) => s.id === DEMO_SCENARIO_ID)?.id ?? scenarios[0]?.id ?? "";
}

function pickDemoAgents(agents: Agent[]): string[] {
  const ids = DEMO_AGENT_IDS.filter((id) => agents.some((agent) => agent.id === id));
  return ids.length ? ids : agents.map((agent) => agent.id);
}

export default function Dashboard() {
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [scenarioId, setScenarioId] = useState("");
  const [ticks, setTicks] = useState(30);
  const [selectedAgentIds, setSelectedAgentIds] = useState<string[]>([]);
  const [agentTypeFilter, setAgentTypeFilter] = useState<AgentTypeFilter>("all");

  const [initLoading, setInitLoading] = useState(true);
  const [initError, setInitError] = useState<string | null>(null);

  const [running, setRunning] = useState(false);
  const [runError, setRunError] = useState<string | null>(null);

  const [remoteName, setRemoteName] = useState("");
  const [remoteEndpoint, setRemoteEndpoint] = useState("");
  const [integration, setIntegration] = useState<IntegrationConfig | null>(null);
  const [integrationWarning, setIntegrationWarning] = useState<string | null>(null);
  const [registering, setRegistering] = useState(false);
  const [registerError, setRegisterError] = useState<string | null>(null);

  const [result, setResult] = useState<SimulationResult | null>(null);
  const [replay, setReplay] = useState<Replay | null>(null);
  const [integrity, setIntegrity] = useState<IntegrityReport | null>(null);
  const [scorecards, setScorecards] = useState<Scorecard[] | null>(null);

  useEffect(() => {
    let active = true;

    (async () => {
      try {
        const loadedScenarios = await api.listScenarios();
        if (active) {
          if (!Array.isArray(loadedScenarios)) {
            throw new Error("GET /api/scenarios did not return an array");
          }
          setScenarios(loadedScenarios);
          setScenarioId(pickDemoScenario(loadedScenarios));
        }
      } catch (error) {
        console.error("[DUAT Arena] Failed to load scenarios:", error);
        if (active) {
          setInitError(error instanceof Error ? error.message : String(error));
        }
      }

      try {
        const loadedAgents = await api.listAgents();
        if (active) {
          if (!Array.isArray(loadedAgents)) {
            throw new Error("GET /api/agents did not return an array");
          }
          setAgents(loadedAgents);
          setSelectedAgentIds(pickDemoAgents(loadedAgents));
        }
      } catch (error) {
        console.error(
          `[DUAT Arena] Failed to load agents from ${API_BASE_URL}/api/agents:`,
          error
        );
        if (active) {
          setInitError((previous) =>
            previous ??
            (error instanceof Error ? error.message : String(error))
          );
        }
      } finally {
        setInitLoading(false);
      }
    })();

    return () => {
      active = false;
    };
  }, []);

  function applyAgentLabPreset(presetIndex: number, config: IntegrationConfig) {
    const preset = AGENT_LAB_PRESETS[presetIndex];
    if (!preset) return;
    setRemoteName(preset.name);
    setRemoteEndpoint(buildAgentLabEndpoint(config.base_url, preset.path));
  }

  useEffect(() => {
    let active = true;
    (async () => {
      const result = await fetchAgentLabIntegrationSafe();
      if (!active) return;
      if (result.config) {
        setIntegration(result.config);
        setIntegrationWarning(null);
        applyAgentLabPreset(1, result.config);
        return;
      }
      const fallback = defaultIntegrationConfig();
      setIntegration(fallback);
      setIntegrationWarning(result.error);
      applyAgentLabPreset(1, fallback);
    })();
    return () => {
      active = false;
    };
  }, []);

  function toggleAgent(id: string) {
    setSelectedAgentIds((previous) =>
      previous.includes(id) ? previous.filter((value) => value !== id) : [...previous, id]
    );
  }

  async function registerRemoteAgent() {
    setRegistering(true);
    setRegisterError(null);
    try {
      const created = await api.registerRemoteAgent({
        name: remoteName.trim(),
        endpoint: remoteEndpoint.trim(),
      });
      const refreshed = await api.listAgents();
      setAgents(refreshed);
      setSelectedAgentIds((previous) =>
        previous.includes(created.id) ? previous : [...previous, created.id]
      );
      setRemoteName("");
      setRemoteEndpoint("");
      if (integration) {
        applyAgentLabPreset(1, integration);
      }
    } catch (error) {
      setRegisterError(error instanceof Error ? error.message : String(error));
    } finally {
      setRegistering(false);
    }
  }

  async function runSimulation() {
    setRunning(true);
    setRunError(null);
    try {
      const runResult = await api.runSimulation({
        scenario_id: scenarioId,
        ticks,
        agent_ids: selectedAgentIds.length ? selectedAgentIds : undefined,
      });
      const [loadedReplay, loadedIntegrity, loadedScorecards] = await Promise.all([
        api.getReplay(runResult.replay_id),
        api.getIntegrity(runResult.replay_id),
        api.getScorecards(runResult.replay_id),
      ]);
      setResult(runResult);
      setReplay(loadedReplay);
      setIntegrity(loadedIntegrity);
      setScorecards(loadedScorecards.scorecards);
    } catch (error) {
      setRunError(error instanceof Error ? error.message : String(error));
    } finally {
      setRunning(false);
    }
  }

  const scenarioName =
    result?.scenario ?? scenarios.find((s) => s.id === scenarioId)?.name ?? scenarioId;

  const visibleAgents = agents.filter((agent) =>
    agentMatchesFilter(resolveAgentType(agent), agentTypeFilter)
  );

  return (
    <main className="shell">
      <section className="hero">
        <p className="eyebrow">DUAT Arena</p>
        <h1>Stress Testing for Trading Bots &amp; AI Agents</h1>
        <p className="summary">
          Test how trading bots and AI agents survive flash crashes, liquidity shocks,
          and panic markets.
        </p>
        <p className="positioning">
          DUAT does not sell trading bots — it grades whether bots and agents survive
          market chaos.
        </p>
      </section>

      {initLoading && <div className="status loading">Loading scenarios and agents…</div>}

      {initError && (
        <div className="status error">
          <p className="error-lead">Could not reach the backend. {initError}</p>
          <p className="error-hint">
            Verify uvicorn is running on localhost:8000. Start it with:{" "}
            <code>uvicorn backend.main:app --reload --port 8000</code>
          </p>
        </div>
      )}

      {!initLoading && !initError && (
        <section className="controls panel controls-panel" aria-label="Simulation controls">
          <div className="control-grid">
            <div className="field">
              <label htmlFor="scenario">Scenario</label>
              <select
                id="scenario"
                value={scenarioId}
                onChange={(event) => setScenarioId(event.target.value)}
                disabled={running}
              >
                {scenarios.map((scenario) => (
                  <option key={scenario.id} value={scenario.id}>
                    {scenario.name}
                  </option>
                ))}
              </select>
            </div>

            <div className="field">
              <label htmlFor="ticks">Ticks</label>
              <input
                id="ticks"
                type="number"
                min={5}
                max={200}
                value={ticks}
                onChange={(event) => setTicks(Number(event.target.value))}
                disabled={running}
              />
            </div>
          </div>

          <div className="field">
            <label>Agents</label>
            <div className="filter-row" role="group" aria-label="Filter agents by type">
              {AGENT_FILTER_OPTIONS.map((option) => (
                <button
                  key={option.id}
                  type="button"
                  className={`filter-chip${agentTypeFilter === option.id ? " active" : ""}`}
                  onClick={() => setAgentTypeFilter(option.id)}
                  disabled={running}
                >
                  {option.label}
                </button>
              ))}
            </div>
            <div className="agent-list">
              {visibleAgents.map((agent) => {
                const agentType = resolveAgentType(agent);
                return (
                  <label
                    className={`agent-chip${selectedAgentIds.includes(agent.id) ? " selected" : ""}`}
                    key={agent.id}
                  >
                    <input
                      type="checkbox"
                      checked={selectedAgentIds.includes(agent.id)}
                      onChange={() => toggleAgent(agent.id)}
                      disabled={running}
                    />
                    <span className="agent-chip-body">
                      <span className="agent-chip-name">
                        {agentLabel(agent.id, agent.name)}
                      </span>
                      <span className="agent-chip-type">{agentTypeLabel(agentType)}</span>
                    </span>
                  </label>
                );
              })}
            </div>
            {visibleAgents.length === 0 && (
              <p className="muted">No agents match this filter.</p>
            )}
          </div>

          <div className="byo">
            <div className="byo-head">
              <label>Bring your own agent</label>
              {integration && (
                <span
                  className={`integration-badge ${
                    integration.mode === "public" ? "public" : "local"
                  }`}
                >
                  {integration.mode === "public"
                    ? "Public URL detected"
                    : "Localhost only"}
                </span>
              )}
            </div>
            <p className="byo-hint">
              Host an endpoint that accepts{" "}
              <code>{`{ tick, market_state, portfolio_snapshot }`}</code> and returns{" "}
              <code>{`{ action, size, reason, confidence }`}</code>. DUAT calls it each
              tick — your model and key stay on your side.
            </p>
            {integrationWarning && (
              <p className="byo-warn">
                Agent Lab integration unavailable ({integrationWarning}). BYO presets
                use local defaults; Arena scenarios and agents are unaffected.
              </p>
            )}
            {integration && (
              <div className="agent-lab-presets" role="group" aria-label="Agent Lab endpoints">
                {AGENT_LAB_PRESETS.map((preset, index) => (
                  <button
                    key={preset.path}
                    type="button"
                    className="preset-chip"
                    onClick={() => applyAgentLabPreset(index, integration)}
                    disabled={registering || running}
                  >
                    {preset.name}
                  </button>
                ))}
              </div>
            )}
            <div className="byo-row">
              <input
                type="text"
                placeholder="Agent name"
                value={remoteName}
                onChange={(event) => setRemoteName(event.target.value)}
                disabled={registering || running}
              />
              <input
                type="text"
                placeholder={
                  integration?.mode === "public"
                    ? "https://your-tunnel.example.com/bots/momentum/decide"
                    : "https://your-agent.example.com/decide"
                }
                value={remoteEndpoint}
                onChange={(event) => setRemoteEndpoint(event.target.value)}
                disabled={registering || running}
              />
              <button
                className="byo-btn"
                onClick={registerRemoteAgent}
                disabled={
                  registering || running || !remoteName.trim() || !remoteEndpoint.trim()
                }
              >
                {registering ? "Registering…" : "Register agent"}
              </button>
            </div>
            {registerError && (
              <p className="byo-error">Registration failed: {registerError}</p>
            )}
          </div>

          <button
            className="run-btn"
            onClick={runSimulation}
            disabled={running || !scenarioId || selectedAgentIds.length === 0}
          >
            {running ? "Running…" : "Run Simulation"}
          </button>

          {selectedAgentIds.length === 0 && (
            <p className="muted">Select at least one agent to run.</p>
          )}
        </section>
      )}

      {running && (
        <div className="status loading">Running simulation and loading results…</div>
      )}

      {runError && <div className="status error">Simulation failed: {runError}</div>}

      {(integrity || scorecards || replay) && (
        <section className="results" aria-label="Simulation results">
          {integrity && <IntegrityPanel integrity={integrity} scenario={scenarioName} />}
          {scorecards && <ScorecardPanel scorecards={scorecards} />}
          {replay && <ReplayTimeline events={replay.events} />}
        </section>
      )}
    </main>
  );
}
