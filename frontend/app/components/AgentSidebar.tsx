"use client";

import Link from "next/link";

import { Agent } from "../../lib/api";
import {
  agentLabel,
  agentTypeLabel,
  connectionStatusEmoji,
  connectionStatusLabel,
  resolveAgentType,
} from "../../lib/format";

interface AgentSidebarProps {
  agents: Agent[];
  selectedAgentIds: string[];
  onToggle: (id: string) => void;
  disabled?: boolean;
}

export default function AgentSidebar({
  agents,
  selectedAgentIds,
  onToggle,
  disabled = false,
}: AgentSidebarProps) {
  const builtins = agents.filter((agent) => agent.kind !== "remote");
  const custom = agents.filter((agent) => agent.kind === "remote");

  return (
    <div className="agent-sidebar">
      <div className="sidebar-head">
        <h2>Agents</h2>
        <Link href="/connect" className="sidebar-link">
          + Connect
        </Link>
      </div>

      <section className="sidebar-section">
        <h3>Built-in</h3>
        <ul className="sidebar-agent-list">
          {builtins.map((agent) => (
            <SidebarAgentRow
              key={agent.id}
              agent={agent}
              checked={selectedAgentIds.includes(agent.id)}
              onToggle={onToggle}
              disabled={disabled}
            />
          ))}
        </ul>
      </section>

      <section className="sidebar-section">
        <h3>Your Agents</h3>
        {custom.length === 0 ? (
          <p className="sidebar-empty">
            No custom agents yet.{" "}
            <Link href="/connect">Connect your first agent</Link>.
          </p>
        ) : (
          <ul className="sidebar-agent-list">
            {custom.map((agent) => (
              <SidebarAgentRow
                key={agent.id}
                agent={agent}
                checked={selectedAgentIds.includes(agent.id)}
                onToggle={onToggle}
                disabled={disabled || agent.enabled === false}
              />
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

function SidebarAgentRow({
  agent,
  checked,
  onToggle,
  disabled,
}: {
  agent: Agent;
  checked: boolean;
  onToggle: (id: string) => void;
  disabled: boolean;
}) {
  const agentType = resolveAgentType(agent);
  const isRemote = agent.kind === "remote";

  return (
    <li>
      <label className={`sidebar-agent${checked ? " selected" : ""}${disabled ? " disabled" : ""}`}>
        <input
          type="checkbox"
          checked={checked}
          onChange={() => onToggle(agent.id)}
          disabled={disabled}
        />
        <span className="sidebar-agent-body">
          <span className="sidebar-agent-name">{agentLabel(agent.id, agent.name)}</span>
          <span className="sidebar-agent-meta">
            <span className="sidebar-agent-type">{agentTypeLabel(agentType)}</span>
            {isRemote && (
              <span className="status-badge" title={connectionStatusLabel(agent.connection_status)}>
                {connectionStatusEmoji(agent.connection_status)}{" "}
                {connectionStatusLabel(agent.connection_status)}
              </span>
            )}
            {agent.enabled === false && (
              <span className="status-badge muted-badge">Disabled</span>
            )}
          </span>
        </span>
      </label>
    </li>
  );
}
