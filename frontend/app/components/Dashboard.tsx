"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";

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
import { isSelectableAgent } from "../../lib/format";
import { consumePendingAgentId } from "../../lib/sessionAgents";
import AgentSidebar from "./AgentSidebar";
import IntegrityPanel from "./IntegrityPanel";
import ReplayTimeline from "./ReplayTimeline";
import ScorecardPanel from "./ScorecardPanel";

const DEMO_SCENARIO_ID = "liquidation-cascade";
const DEMO_AGENT_IDS = ["agent-conservative-001", "agent-llm-momentum-001"];

function pickDemoScenario(scenarios: Scenario[]): string {
  return scenarios.find((s) => s.id === DEMO_SCENARIO_ID)?.id ?? scenarios[0]?.id ?? "";
}

function pickDemoAgents(agents: Agent[]): string[] {
  const ids = DEMO_AGENT_IDS.filter((id) =>
    agents.some((agent) => agent.id === id && isSelectableAgent(agent))
  );
  if (ids.length) return ids;
  return agents.filter(isSelectableAgent).map((agent) => agent.id);
}

export default function Dashboard() {
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [scenarioId, setScenarioId] = useState("");
  const [ticks, setTicks] = useState(30);
  const [selectedAgentIds, setSelectedAgentIds] = useState<string[]>([]);

  const [initLoading, setInitLoading] = useState(true);
  const [initError, setInitError] = useState<string | null>(null);

  const [running, setRunning] = useState(false);
  const [runError, setRunError] = useState<string | null>(null);

  const [result, setResult] = useState<SimulationResult | null>(null);
  const [replay, setReplay] = useState<Replay | null>(null);
  const [integrity, setIntegrity] = useState<IntegrityReport | null>(null);
  const [scorecards, setScorecards] = useState<Scorecard[] | null>(null);

  const resultsRef = useRef<HTMLElement>(null);
  const statusRef = useRef<HTMLDivElement>(null);

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
          const pendingId = consumePendingAgentId();
          const demoIds = pickDemoAgents(loadedAgents);
          if (
            pendingId &&
            loadedAgents.some(
              (agent) => agent.id === pendingId && isSelectableAgent(agent)
            )
          ) {
            setSelectedAgentIds(
              demoIds.includes(pendingId) ? demoIds : [...demoIds, pendingId]
            );
          } else {
            setSelectedAgentIds(demoIds);
          }
        }
      } catch (error) {
        console.error(
          `[DUAT Arena] Failed to load agents from ${API_BASE_URL}/api/agents:`,
          error
        );
        if (active) {
          setInitError((previous) =>
            previous ?? (error instanceof Error ? error.message : String(error))
          );
        }
      } finally {
        setInitLoading(false);
      }
    })();

    async function refreshAgentsOnFocus() {
      try {
        const loadedAgents = await api.listAgents();
        if (!Array.isArray(loadedAgents)) return;
        setAgents(loadedAgents);
        setSelectedAgentIds((previous) =>
          previous.filter((id) =>
            loadedAgents.some((agent) => agent.id === id && isSelectableAgent(agent))
          )
        );
      } catch {
        // Ignore background refresh errors.
      }
    }

    window.addEventListener("focus", refreshAgentsOnFocus);

    return () => {
      active = false;
      window.removeEventListener("focus", refreshAgentsOnFocus);
    };
  }, []);

  function toggleAgent(id: string) {
    setSelectedAgentIds((previous) =>
      previous.includes(id) ? previous.filter((value) => value !== id) : [...previous, id]
    );
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

  useEffect(() => {
    if (running) {
      statusRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }
  }, [running]);

  useEffect(() => {
    if (result && (integrity || scorecards || replay)) {
      resultsRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }, [result, integrity, scorecards, replay]);

  useEffect(() => {
    if (runError) {
      statusRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }
  }, [runError]);

  return (
    <div className="app-body with-sidebar">
      <aside className="app-sidebar">
        <AgentSidebar
          agents={agents}
          selectedAgentIds={selectedAgentIds}
          onToggle={toggleAgent}
          disabled={running}
        />
      </aside>

      <main className="app-main shell">
        <section className="hero">
          <p className="eyebrow">DUAT Arena</p>
          <h1>Stress Testing for Trading Bots &amp; AI Agents</h1>
          <p className="summary">
            Select agents in the sidebar, pick a chaos scenario, and run a deterministic
            stress test. DUAT grades survival — it does not build or host agents.
          </p>
          <p className="positioning">
            <Link href="/connect">Connect your agent</Link>
            {" · "}
            <Link href="/docs">Integration docs</Link>
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

            <button
              className="run-btn"
              onClick={runSimulation}
              disabled={running || !scenarioId || selectedAgentIds.length === 0}
            >
              {running ? "Running…" : "Run Simulation"}
            </button>

            {selectedAgentIds.length === 0 && (
              <p className="muted">Select at least one agent in the sidebar.</p>
            )}
          </section>
        )}

        {running && (
          <div ref={statusRef} className="status loading">
            Running simulation and loading results…
          </div>
        )}

        {runError && (
          <div ref={statusRef} className="status error">
            Simulation failed: {runError}
          </div>
        )}

        {(integrity || scorecards || replay) && (
          <section ref={resultsRef} className="results" aria-label="Simulation results">
            {integrity && <IntegrityPanel integrity={integrity} scenario={scenarioName} />}
            {scorecards && <ScorecardPanel scorecards={scorecards} />}
            {replay && <ReplayTimeline events={replay.events} />}
          </section>
        )}
      </main>
    </div>
  );
}
