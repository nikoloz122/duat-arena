/** Agent Lab integration URLs for Arena BYO registration pre-fill. */

function resolveAgentLabBase(): string {
  const fromEnv = process.env.NEXT_PUBLIC_AGENT_LAB_URL?.trim();
  if (fromEnv) return fromEnv.replace(/\/$/, "");
  return "http://localhost:8001";
}

export const AGENT_LAB_BASE = resolveAgentLabBase();

export interface AgentLabPreset {
  name: string;
  path: string;
}

export const AGENT_LAB_PRESETS: AgentLabPreset[] = [
  { name: "Risk Manager Bot", path: "/bots/risk-manager/decide" },
  { name: "Momentum Bot", path: "/bots/momentum/decide" },
  { name: "Dip Buyer Bot", path: "/bots/dip-buyer/decide" },
  { name: "LLM Market Agent", path: "/agents/llm/decide" },
  { name: "LLM Momentum Agent v2", path: "/agents/llm-momentum-v2/decide" },
];

export interface IntegrationConfig {
  base_url: string;
  mode: "public" | "local";
}

export function buildAgentLabEndpoint(baseUrl: string, path: string): string {
  return `${baseUrl.replace(/\/$/, "")}${path}`;
}

export function getAgentLabIntegrationUrl(): string {
  return `${AGENT_LAB_BASE}/integration`;
}

const INTEGRATION_TIMEOUT_MS = 5000;

export async function fetchAgentLabIntegration(): Promise<IntegrationConfig> {
  const url = getAgentLabIntegrationUrl();
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), INTEGRATION_TIMEOUT_MS);

  try {
    const response = await fetch(url, {
      headers: { Accept: "application/json" },
      signal: controller.signal,
    });
    if (!response.ok) {
      throw new Error(`${response.status} ${response.statusText} at ${url}`);
    }
    return (await response.json()) as IntegrationConfig;
  } catch (error) {
    if (error instanceof Error && error.name === "AbortError") {
      throw new Error(`Timed out after ${INTEGRATION_TIMEOUT_MS}ms at ${url}`);
    }
    throw error;
  } finally {
    clearTimeout(timeout);
  }
}

/** Non-blocking fetch for dashboard startup — never throws. */
export async function fetchAgentLabIntegrationSafe(): Promise<{
  config: IntegrationConfig | null;
  error: string | null;
  url: string;
}> {
  const url = getAgentLabIntegrationUrl();
  try {
    const config = await fetchAgentLabIntegration();
    return { config, error: null, url };
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    console.warn(`[DUAT Arena] Agent Lab integration unavailable: ${url} — ${message}`);
    return { config: null, error: `${url} — ${message}`, url };
  }
}

export function defaultIntegrationConfig(): IntegrationConfig {
  return { base_url: AGENT_LAB_BASE, mode: "local" };
}
