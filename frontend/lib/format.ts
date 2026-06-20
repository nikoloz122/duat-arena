// Presentation helpers shared by the dashboard panels. Agent display names and
// agent_type metadata are derived client-side from id + kind — no backend changes.

export const GRADE_COLORS: Record<string, string> = {
  A: "#1a7f37",
  B: "#2da44e",
  C: "#bf8700",
  D: "#cf6800",
  F: "#cf222e",
};

export const SEVERITY_COLORS: Record<string, string> = {
  high: "#cf222e",
  medium: "#bf8700",
};

export type AgentType =
  | "trading_bot"
  | "rule_based_bot"
  | "llm_agent"
  | "custom_api_bot";

export type AgentTypeFilter = "all" | "trading_bots" | "ai_agents" | "custom_api";

const AGENT_DISPLAY_NAMES: Record<string, string> = {
  "agent-conservative-001": "Conservative Rule-Based Bot",
  "agent-momentum-001": "Momentum Trading Bot",
  "agent-panic-seller-001": "Panic Seller Bot",
  "agent-llm-momentum-001": "LLM Momentum Agent",
};

const AGENT_TYPE_BY_ID: Record<string, AgentType> = {
  "agent-conservative-001": "rule_based_bot",
  "agent-momentum-001": "trading_bot",
  "agent-panic-seller-001": "trading_bot",
  "agent-llm-momentum-001": "llm_agent",
};

export const AGENT_TYPE_LABELS: Record<AgentType, string> = {
  trading_bot: "Trading Bot",
  rule_based_bot: "Rule-Based Bot",
  llm_agent: "AI Agent",
  custom_api_bot: "Custom API Bot",
};

export const AGENT_FILTER_OPTIONS: { id: AgentTypeFilter; label: string }[] = [
  { id: "all", label: "All" },
  { id: "trading_bots", label: "Trading Bots" },
  { id: "ai_agents", label: "AI Agents" },
  { id: "custom_api", label: "Custom API" },
];

export function gradeColor(grade: string): string {
  return GRADE_COLORS[grade] ?? "#57606a";
}

export function severityColor(severity: string): string {
  return SEVERITY_COLORS[severity] ?? "#57606a";
}

export function resolveAgentType(agent: { id: string; kind?: string }): AgentType {
  if (agent.kind === "remote") return "custom_api_bot";
  return AGENT_TYPE_BY_ID[agent.id] ?? "trading_bot";
}

export function agentTypeLabel(type: AgentType): string {
  return AGENT_TYPE_LABELS[type];
}

export function agentMatchesFilter(type: AgentType, filter: AgentTypeFilter): boolean {
  if (filter === "all") return true;
  if (filter === "trading_bots") {
    return type === "trading_bot" || type === "rule_based_bot";
  }
  if (filter === "ai_agents") return type === "llm_agent";
  return type === "custom_api_bot";
}

export function agentLabel(id: string, name?: string): string {
  if (!id) return "Unknown Bot / Agent";
  if (AGENT_DISPLAY_NAMES[id]) return AGENT_DISPLAY_NAMES[id];
  if (name?.trim()) return name.trim();
  const core = id.replace(/^agent-/, "").replace(/-\d+$/, "");
  const label = core
    .split("-")
    .map((word) => (word ? word[0].toUpperCase() + word.slice(1) : word))
    .join(" ");
  return label.endsWith("Agent") || label.endsWith("Bot") ? label : `${label} Agent`;
}
