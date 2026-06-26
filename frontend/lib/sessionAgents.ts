/** Persist BYOA selection across Connect → Arena navigation (same browser tab). */

const PENDING_AGENT_KEY = "duat-pending-agent-id";

export function stashPendingAgentId(agentId: string): void {
  if (typeof window === "undefined") return;
  sessionStorage.setItem(PENDING_AGENT_KEY, agentId);
}

export function consumePendingAgentId(): string | null {
  if (typeof window === "undefined") return null;
  const value = sessionStorage.getItem(PENDING_AGENT_KEY);
  if (value) {
    sessionStorage.removeItem(PENDING_AGENT_KEY);
  }
  return value;
}
