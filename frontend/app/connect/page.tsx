"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import {
  Agent,
  AuthType,
  RemoteAgentRequest,
  TestConnectionResult,
  api,
} from "../../lib/api";
import { stashPendingAgentId } from "../../lib/sessionAgents";
import {
  connectionStatusEmoji,
  connectionStatusLabel,
} from "../../lib/format";

const AUTH_OPTIONS: { value: AuthType; label: string }[] = [
  { value: "none", label: "None" },
  { value: "api_key", label: "API Key" },
  { value: "bearer", label: "Bearer Token" },
];

const DEFAULT_TIMEOUT = 5;

const EMPTY_FORM: RemoteAgentRequest = {
  name: "",
  endpoint: "",
  auth_type: "none",
  secret: "",
  timeout: DEFAULT_TIMEOUT,
};

export default function ConnectAgentPage() {
  const router = useRouter();
  const [agents, setAgents] = useState<Agent[]>([]);
  const [form, setForm] = useState<RemoteAgentRequest>(EMPTY_FORM);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [baselineEndpoint, setBaselineEndpoint] = useState("");
  const [baselineAuthType, setBaselineAuthType] = useState<AuthType>("none");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [testResult, setTestResult] = useState<TestConnectionResult | null>(null);

  const connectionChanged = useMemo(() => {
    if (!editingId) return true;
    const authChanged = (form.auth_type ?? "none") !== baselineAuthType;
    const endpointChanged = form.endpoint.trim() !== baselineEndpoint;
    const secretChanged = Boolean(form.secret?.trim());
    return authChanged || endpointChanged || secretChanged;
  }, [baselineAuthType, baselineEndpoint, editingId, form]);

  const canSave = useMemo(() => {
    if (!form.name.trim() || !form.endpoint.trim()) return false;
    if (form.auth_type !== "none" && !form.secret?.trim() && !editingId) return false;
    if (!editingId) return testResult?.success === true;
    if (connectionChanged) return testResult?.success === true;
    return true;
  }, [connectionChanged, editingId, form, testResult]);

  async function refreshAgents() {
    const loaded = await api.listAgents();
    setAgents(loaded.filter((agent) => agent.kind === "remote"));
  }

  useEffect(() => {
    refreshAgents()
      .catch((err) => setError(err instanceof Error ? err.message : String(err)))
      .finally(() => setLoading(false));
  }, []);

  function updateField<K extends keyof RemoteAgentRequest>(
    key: K,
    value: RemoteAgentRequest[K]
  ) {
    setForm((previous) => ({ ...previous, [key]: value }));
    setTestResult(null);
  }

  function startEdit(agent: Agent) {
    setEditingId(agent.id);
    setBaselineEndpoint(agent.endpoint ?? "");
    setBaselineAuthType(agent.auth_type ?? "none");
    setForm({
      name: agent.name,
      endpoint: agent.endpoint ?? "",
      auth_type: agent.auth_type ?? "none",
      secret: "",
      timeout: agent.timeout ?? DEFAULT_TIMEOUT,
      description: agent.description,
    });
    setTestResult(null);
    setError(null);
  }

  function resetForm() {
    setEditingId(null);
    setBaselineEndpoint("");
    setBaselineAuthType("none");
    setForm(EMPTY_FORM);
    setTestResult(null);
    setError(null);
  }

  async function handleTest() {
    setTesting(true);
    setError(null);
    setTestResult(null);
    try {
      const result = await api.testConnection({
        endpoint: form.endpoint.trim(),
        auth_type: form.auth_type,
        secret: form.secret?.trim() || undefined,
        timeout: form.timeout,
        agent_id: editingId ?? undefined,
      });
      setTestResult(result);
      if (editingId) await refreshAgents();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setTesting(false);
    }
  }

  async function handleSave(event: React.FormEvent) {
    event.preventDefault();
    if (!canSave) return;

    setSaving(true);
    setError(null);
    try {
      const payload: RemoteAgentRequest = {
        name: form.name.trim(),
        endpoint: form.endpoint.trim(),
        auth_type: form.auth_type,
        timeout: form.timeout ?? DEFAULT_TIMEOUT,
        description: form.description?.trim() || undefined,
      };
      if (form.secret?.trim()) {
        payload.secret = form.secret.trim();
      }

      if (editingId) {
        await api.updateRemoteAgent(editingId, payload);
        await refreshAgents();
        setBaselineEndpoint(form.endpoint.trim());
        setBaselineAuthType(form.auth_type ?? "none");
        setTestResult(null);
      } else {
        const created = await api.registerRemoteAgent(payload);
        stashPendingAgentId(created.id);
        router.push("/");
        return;
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(agentId: string) {
    if (!window.confirm("Delete this agent? This cannot be undone.")) return;
    setError(null);
    try {
      await api.deleteRemoteAgent(agentId);
      if (editingId === agentId) resetForm();
      await refreshAgents();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  async function handleToggleEnabled(agent: Agent) {
    setError(null);
    try {
      if (agent.enabled === false) {
        await api.enableRemoteAgent(agent.id);
      } else {
        await api.disableRemoteAgent(agent.id);
      }
      await refreshAgents();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  async function handleRetest(agentId: string) {
    setError(null);
    try {
      const result = await api.retestRemoteAgent(agentId);
      setTestResult(result);
      await refreshAgents();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  return (
    <main className="page-content">
      <section className="page-hero">
        <p className="eyebrow">Bring Your Own Agent</p>
        <h1>Connect Your Agent</h1>
        <p className="summary">
          Point DUAT at your existing <code>POST /decide</code> endpoint. We stress-test
          it under market chaos and grade reliability — your agent stays on your
          infrastructure.
        </p>
        <p className="page-links">
          <Link href="/docs">View API Documentation</Link>
          {" · "}
          <Link href="/">Run Simulation</Link>
        </p>
      </section>

      <div className="connect-grid">
        <form className="panel connect-form" onSubmit={handleSave}>
          <h2>{editingId ? "Edit Agent" : "Connect Agent"}</h2>
          <p className="form-intro">
            Name your agent, paste its public URL, test the connection, then save.
          </p>

          <div className="field">
            <label htmlFor="agent-name">Agent Name</label>
            <input
              id="agent-name"
              type="text"
              value={form.name}
              onChange={(event) => updateField("name", event.target.value)}
              placeholder="My Trading Agent"
              required
            />
          </div>

          <div className="field">
            <label htmlFor="agent-endpoint">Endpoint URL</label>
            <input
              id="agent-endpoint"
              type="url"
              value={form.endpoint}
              onChange={(event) => updateField("endpoint", event.target.value)}
              placeholder="https://your-agent.example.com/decide"
              required
            />
          </div>

          <div className="field">
            <label htmlFor="agent-auth">Authentication (optional)</label>
            <select
              id="agent-auth"
              value={form.auth_type}
              onChange={(event) =>
                updateField("auth_type", event.target.value as AuthType)
              }
            >
              {AUTH_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>

          {form.auth_type !== "none" && (
            <div className="field">
              <label htmlFor="agent-secret">
                Secret {editingId ? "(leave blank to keep existing)" : ""}
              </label>
              <input
                id="agent-secret"
                type="password"
                value={form.secret ?? ""}
                onChange={(event) => updateField("secret", event.target.value)}
                placeholder={
                  form.auth_type === "api_key" ? "Your API key" : "Bearer token"
                }
                autoComplete="off"
              />
            </div>
          )}

          <details className="advanced-block">
            <summary>Advanced options</summary>
            <div className="field">
              <label htmlFor="agent-description">Description</label>
              <textarea
                id="agent-description"
                value={form.description ?? ""}
                onChange={(event) => updateField("description", event.target.value)}
                placeholder="Optional note for your own reference"
                rows={2}
              />
            </div>
            <div className="field">
              <label htmlFor="agent-timeout">Timeout (seconds)</label>
              <input
                id="agent-timeout"
                type="number"
                min={1}
                max={30}
                step={0.5}
                value={form.timeout ?? DEFAULT_TIMEOUT}
                onChange={(event) => updateField("timeout", Number(event.target.value))}
              />
            </div>
          </details>

          <div className="form-actions">
            <button
              type="button"
              className="secondary-btn"
              onClick={handleTest}
              disabled={testing || !form.endpoint.trim()}
            >
              {testing ? "Testing…" : "Test Connection"}
            </button>
            <button type="submit" className="run-btn" disabled={saving || !canSave}>
              {saving ? "Saving…" : editingId ? "Save Changes" : "Save Agent"}
            </button>
            {editingId && (
              <button type="button" className="ghost-btn" onClick={resetForm}>
                Cancel
              </button>
            )}
          </div>

          {!canSave && form.name.trim() && form.endpoint.trim() && (
            <p className="field-hint">
              Run a successful Test Connection before saving
              {editingId && connectionChanged ? " changed endpoint settings" : ""}.
            </p>
          )}

          {error && <p className="form-error">{error}</p>}

          {testResult && (
            <div className={`test-result ${testResult.success ? "ok" : "fail"}`}>
              <p className="test-result-head">
                {testResult.success ? "Connection successful" : "Connection failed"}
                {testResult.latency_ms != null && ` · ${testResult.latency_ms} ms`}
                {" · "}
                {connectionStatusEmoji(testResult.connection_status)}{" "}
                {connectionStatusLabel(testResult.connection_status)}
              </p>
              {testResult.status_code != null && (
                <p className="test-meta">HTTP {testResult.status_code}</p>
              )}
              {testResult.errors.length > 0 && (
                <ul className="test-errors">
                  {testResult.errors.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </form>

        {agents.length > 0 && (
          <section className="panel registered-panel">
            <h2>Your Connected Agents</h2>
            {loading && <p className="muted">Loading…</p>}
            <ul className="registered-list">
              {agents.map((agent) => (
                <li key={agent.id} className="registered-card">
                  <div className="registered-head">
                    <div>
                      <h3>{agent.name}</h3>
                    </div>
                    <span className="status-badge">
                      {connectionStatusEmoji(agent.connection_status)}{" "}
                      {connectionStatusLabel(agent.connection_status)}
                    </span>
                  </div>
                  <p className="registered-endpoint">{agent.endpoint}</p>
                  <div className="registered-actions">
                    <button type="button" onClick={() => startEdit(agent)}>
                      Edit
                    </button>
                    <button type="button" onClick={() => handleRetest(agent.id)}>
                      Retest
                    </button>
                    <button type="button" onClick={() => handleToggleEnabled(agent)}>
                      {agent.enabled === false ? "Enable" : "Disable"}
                    </button>
                    <button
                      type="button"
                      className="danger-btn"
                      onClick={() => handleDelete(agent.id)}
                    >
                      Delete
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          </section>
        )}
      </div>
    </main>
  );
}
