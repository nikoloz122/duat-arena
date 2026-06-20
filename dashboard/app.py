import json
import sys
from pathlib import Path

import requests
import streamlit as st

import api_client

# The dashboard reuses the engine's pure integrity/scorecard logic (single
# source of truth) rather than re-deriving it, so make the project root
# importable when Streamlit runs this file from the dashboard dir.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from simulation import integrity
from simulation.scorecard import build_scorecards

FALLBACK_SCENARIOS = [
    {"id": "flash-crash", "name": "Flash Crash"},
    {"id": "liquidity-drain", "name": "Liquidity Drain"},
    {"id": "panic-contagion", "name": "Panic Contagion"},
    {"id": "oracle-failure", "name": "Oracle Failure"},
    {"id": "stablecoin-depeg", "name": "Stablecoin Depeg (UST/LUNA-style)"},
    {"id": "liquidation-cascade", "name": "Liquidation Cascade"},
]

TERMINAL_STATUSES = ("failed", "liquidated")

GRADE_COLORS = {
    "A": "#1a7f37",
    "B": "#2da44e",
    "C": "#bf8700",
    "D": "#cf6800",
    "F": "#cf222e",
}

SEVERITY_COLORS = {
    "high": "#cf222e",
    "medium": "#bf8700",
}


def load_scenarios() -> list[dict[str, str]]:
    try:
        scenarios = api_client.list_scenarios()
        if scenarios:
            return scenarios
    except requests.RequestException:
        st.sidebar.warning("Could not reach backend for scenarios. Using defaults.")
    return FALLBACK_SCENARIOS


def load_agents() -> list[dict[str, str]]:
    """Registered agents from the backend, or an empty list if unreachable."""
    try:
        agents = api_client.list_agents()
        if agents:
            return agents
    except requests.RequestException:
        st.sidebar.info("Agent selection unavailable (backend unreachable). Using default presets.")
    return []


def _agent_label(agent_id: str) -> str:
    if not agent_id:
        return "Unknown Agent"
    core = agent_id.replace("agent-", "")
    core = core.rsplit("-", 1)[0] if "-" in core else core
    label = core.replace("-", " ").title()
    if not label.endswith("Agent"):
        label = f"{label} Agent"
    return label


def _pct(value: float) -> str:
    return f"{round(float(value) * 100, 2)}%"


def _merge_reports(summary: dict) -> list[dict]:
    agent_reports = summary.get("agent_reports", []) or []
    failure_reports = {f.get("agent_id"): f for f in summary.get("failure_reports", []) or []}
    reliability_reports = {
        r.get("agent_id"): r for r in summary.get("reliability_reports", []) or []
    }

    merged = []
    for report in agent_reports:
        agent_id = report.get("agent_id")
        merged.append(
            {
                **report,
                "failure": failure_reports.get(agent_id, {}),
                "reliability": reliability_reports.get(agent_id, {}),
            }
        )
    return merged


def _ranked_reports(summary: dict) -> list[dict]:
    return sorted(_merge_reports(summary), key=lambda r: r.get("equity", 0.0), reverse=True)


def _reliability_ranked(summary: dict) -> list[dict]:
    """Merged reports that carry a reliability score, best score first."""
    scored = [r for r in _merge_reports(summary) if r.get("reliability")]
    return sorted(
        scored, key=lambda r: r["reliability"].get("score", 0.0), reverse=True
    )


def render_reliability_headline(summary: dict) -> None:
    ranked = _reliability_ranked(summary)
    if not ranked:
        return

    st.subheader("Reliability Score")
    st.caption("How reliable was each agent under stress (0–100). Higher is more reliable.")

    cols = st.columns(len(ranked))
    for col, report in zip(cols, ranked):
        reliability = report.get("reliability", {})
        score = reliability.get("score", 0.0)
        grade = reliability.get("grade", "—")
        color = GRADE_COLORS.get(grade, "#57606a")

        col.metric(_agent_label(report.get("agent_id")), score)
        col.markdown(
            "<div style='text-align:center;margin-top:-8px;'>"
            f"<span style='background:{color};color:#ffffff;padding:2px 12px;"
            "border-radius:6px;font-weight:700;'>"
            f"Grade {grade}</span></div>",
            unsafe_allow_html=True,
        )


def render_integrity_headline(summary: dict, events: list[dict]) -> None:
    """Lead banner: how many unsafe AI decisions DUAT caught at the boundary."""
    violations = integrity.categorize_events(events)
    scenario = str(summary.get("scenario", "the scenario"))
    intercepted = violations.get("intervention_ticks", 0)

    if intercepted <= 0:
        st.success(
            f"DUAT intercepted 0 unsafe decisions during {scenario}. "
            "Every agent decision passed the safety boundary unchanged."
        )
        return

    st.error(
        f"DUAT intercepted {intercepted} unsafe AI decision(s) during {scenario}."
    )
    high = sum(c["count"] for c in violations["categories"] if c["severity"] == "high")
    medium = sum(c["count"] for c in violations["categories"] if c["severity"] == "medium")
    st.caption(
        f"{high} high-severity · {medium} medium-severity intervention reason(s). "
        "Each unsafe decision was normalized to a safe action before it reached the market."
    )


def _severity_badge(count: int, label: str, severity: str) -> str:
    color = SEVERITY_COLORS.get(severity, "#57606a")
    return (
        f"<span style='background:{color};color:#ffffff;padding:2px 10px;"
        f"border-radius:6px;font-weight:600;margin-right:6px;'>"
        f"{count}× {label}</span>"
    )


def render_integrity_breakdown(summary: dict, events: list[dict]) -> None:
    """Categorized, color-coded view of real boundary interceptions + timeline."""
    violations = integrity.categorize_events(events)
    if violations.get("total", 0) <= 0:
        return

    st.subheader("Integrity Violations")
    badges = " ".join(
        _severity_badge(c["count"], c["label"], c["severity"])
        for c in violations["categories"]
    )
    st.markdown(badges, unsafe_allow_html=True)

    with st.expander("Per-tick integrity events", expanded=False):
        rows = [
            {
                "Tick": entry["tick"],
                "Agent": _agent_label(entry["agent"]),
                "Category": entry["label"],
                "Severity": entry["severity"],
                "Detail": entry["note"],
            }
            for entry in violations["timeline"]
        ]
        st.dataframe(rows, use_container_width=True)


def render_scorecards(summary: dict, events: list[dict]) -> None:
    """Per-agent reliability scorecard: six categories, why-this-grade, JSON export."""
    cards = build_scorecards(summary, events)
    if not cards:
        return

    cards = sorted(cards, key=lambda c: c.get("score") or 0.0, reverse=True)

    st.subheader("Agent Reliability Scorecards")
    st.caption("Moody's-style reliability report per agent. Higher is more reliable (0–100).")

    for card in cards:
        grade = card.get("grade", "—")
        score = card.get("score")
        color = GRADE_COLORS.get(grade, "#57606a")
        label = f"{_agent_label(card.get('agent_id'))} · {score} (Grade {grade})"

        with st.expander(label, expanded=card.get("status") in TERMINAL_STATUSES):
            st.markdown(
                f"<span style='background:{color};color:#ffffff;padding:3px 14px;"
                f"border-radius:6px;font-weight:700;'>Grade {grade} · {score}/100</span>",
                unsafe_allow_html=True,
            )

            categories = card.get("categories", {}) or {}
            labels = card.get("category_labels", {}) or {}
            for key in card.get("category_order", []):
                if key not in categories:
                    continue
                value = max(0.0, min(1.0, float(categories[key])))
                st.caption(f"{labels.get(key, key)}: {round(value, 2)}")
                st.progress(value)

            integ = card.get("integrity", {}) or {}
            intercepted = integ.get("intervention_ticks", 0)
            if intercepted:
                st.markdown(f"**Decision-boundary interceptions:** {intercepted}")

            explanation = card.get("explanation", []) or []
            if explanation:
                st.write("Why this grade:")
                for line in explanation:
                    st.markdown(f"- {line}")

            st.download_button(
                "Download scorecard JSON",
                data=json.dumps(card, indent=2),
                file_name=f"scorecard-{card.get('agent_id')}.json",
                mime="application/json",
                key=f"scorecard-download-{card.get('agent_id')}",
            )


def render_outcome_banner(summary: dict) -> None:
    ranked = _ranked_reports(summary)
    if not ranked:
        return

    scenario = str(summary.get("scenario", "Simulation")).upper()
    best = ranked[0]
    failed = [r for r in ranked if r.get("status") in TERMINAL_STATUSES]

    lines = [f"### {scenario} RESULT"]
    if failed:
        worst_failed = max(failed, key=lambda r: r.get("max_drawdown", 0.0))
        lines.append(
            f"**{_agent_label(worst_failed.get('agent_id'))} "
            f"{worst_failed.get('status', 'failed').upper()}** — "
            f"Max Drawdown {_pct(worst_failed.get('max_drawdown', 0.0))}"
        )
    else:
        lines.append("**All agents survived** the stress scenario.")

    lines.append(f"{_agent_label(best.get('agent_id'))} survived best")
    lines.append(f"Final Equity Leader: ${best.get('equity')}")

    body = "  \n".join(lines)
    if failed:
        st.error(body)
    else:
        st.success(body)


def render_key_findings(summary: dict) -> None:
    ranked = _ranked_reports(summary)
    if not ranked:
        return

    st.subheader("Key Findings")

    best = ranked[0]
    worst = ranked[-1]
    failed = [r for r in ranked if r.get("status") in TERMINAL_STATUSES]

    findings: list[str] = []
    findings.append(
        f"{_agent_label(best.get('agent_id'))} preserved the most capital "
        f"(equity ${best.get('equity')})."
    )
    for agent in failed:
        findings.append(
            f"{_agent_label(agent.get('agent_id'))} exceeded the failure threshold "
            f"(max drawdown {_pct(agent.get('max_drawdown', 0.0))})."
        )
    if worst.get("agent_id") != best.get("agent_id"):
        findings.append(
            f"{_agent_label(worst.get('agent_id'))} ended with the lowest equity "
            f"(${worst.get('equity')})."
        )
    if len(ranked) >= 3:
        middle = ranked[1]
        if middle.get("status") not in TERMINAL_STATUSES:
            findings.append(
                f"{_agent_label(middle.get('agent_id'))} reduced losses but underperformed "
                f"{_agent_label(best.get('agent_id'))}."
            )
    if failed:
        findings.append("At least one agent failed during stress conditions.")

    for finding in findings[:5]:
        st.markdown(f"- {finding}")


def render_headline_metrics(summary: dict) -> None:
    ranked = _ranked_reports(summary)
    if not ranked:
        return

    best = ranked[0]
    worst = ranked[-1]
    failed = [r for r in ranked if r.get("status") in TERMINAL_STATUSES]
    highest_dd = max(ranked, key=lambda r: r.get("max_drawdown", 0.0))

    cols = st.columns(4)
    cols[0].metric("Failed Agents", len(failed))
    cols[1].metric("Best Survivor", _agent_label(best.get("agent_id")), f"${best.get('equity')}")
    cols[2].metric("Worst Performer", _agent_label(worst.get("agent_id")), f"${worst.get('equity')}")
    cols[3].metric("Highest Drawdown", _pct(highest_dd.get("max_drawdown", 0.0)))


def render_agent_outcomes(summary: dict) -> None:
    st.subheader("Agent Outcomes")

    ranked = _ranked_reports(summary)
    if not ranked:
        st.info("No agent outcomes available for this run.")
        return

    table_rows = [
        {
            "Agent": _agent_label(r.get("agent_id")),
            "Status": r.get("status"),
            "Final Equity": r.get("equity"),
            "Realized PnL": r.get("realized_pnl"),
            "Max Drawdown": _pct(r.get("max_drawdown", 0.0)),
        }
        for r in ranked
    ]
    st.dataframe(table_rows, use_container_width=True)

    st.subheader("Failure Analysis")
    for r in ranked:
        failure = r.get("failure", {})
        status = r.get("status")
        label = f"{_agent_label(r.get('agent_id'))} · {status}"

        with st.expander(label, expanded=status in TERMINAL_STATUSES):
            if status in TERMINAL_STATUSES:
                st.error(failure.get("summary", ""))
            else:
                st.success(failure.get("summary", ""))

            primary = failure.get("primary_failure_reason")
            if primary:
                st.write(f"Primary failure reason: {primary}")

            risk_flags = failure.get("risk_flags", [])
            st.write("Risk flags: " + (", ".join(risk_flags) if risk_flags else "none"))

            fixes = failure.get("recommended_fix", [])
            if fixes:
                st.write("Recommended fix:")
                for fix in fixes:
                    st.write(f"- {fix}")


def _derive_key_events(events: list[dict]) -> list[dict]:
    key_events: list[dict] = []
    seen_chaos_ticks: set[int] = set()
    seen_terminal_agents: set[str] = set()

    for event in events:
        tick = event.get("tick")

        scenario_event = event.get("scenario_event")
        if scenario_event and tick not in seen_chaos_ticks:
            seen_chaos_ticks.add(tick)
            shock = (scenario_event.get("payload", {}) or {}).get("shock", "chaos event")
            key_events.append({"tick": tick, "text": f"{shock.replace('_', ' ').title()} triggered"})

        portfolio = event.get("portfolio_state") or {}
        status = portfolio.get("status")
        agent_id = event.get("agent")
        if status in TERMINAL_STATUSES and agent_id not in seen_terminal_agents:
            seen_terminal_agents.add(agent_id)
            key_events.append(
                {"tick": tick, "text": f"{_agent_label(agent_id)} status changed to {status.upper()}"}
            )

    return sorted(key_events, key=lambda e: (e.get("tick") if e.get("tick") is not None else 0))


def render_key_events(events: list[dict]) -> None:
    if not events:
        return

    key_events = _derive_key_events(events)
    if not key_events:
        return

    st.subheader("Key Events")
    for event in key_events:
        st.markdown(f"- **Tick {event['tick']}** — {event['text']}")


def render_timeline(events: list[dict]) -> None:
    if not events:
        return

    with st.expander("Replay Timeline", expanded=False):
        for event in events:
            marker = " 🔻 chaos event" if event.get("scenario_event") else ""
            label = f"Tick {event.get('tick')} · {_agent_label(event.get('agent'))} · {event.get('action')}{marker}"
            with st.expander(label):
                st.write(event.get("reason", ""))
                st.json(event.get("market_state", {}))
                if event.get("scenario_event"):
                    st.json(event["scenario_event"])


def render_agent_actions(events: list[dict]) -> None:
    if not events:
        return

    with st.expander("Agent Actions", expanded=False):
        rows = []
        for event in events:
            market_state = event.get("market_state") or {}
            rows.append(
                {
                    "tick": event.get("tick"),
                    "agent": _agent_label(event.get("agent")),
                    "action": event.get("action"),
                    "reason": event.get("reason", ""),
                    "price": market_state.get("current_price"),
                    "liquidity": market_state.get("liquidity"),
                }
            )
        st.dataframe(rows, use_container_width=True)


def render_market_details(summary: dict) -> None:
    with st.expander("Market Details", expanded=False):
        cols = st.columns(3)
        cols[0].metric("Final Price", summary.get("final_price"))
        cols[1].metric("Final Liquidity", summary.get("final_liquidity"))
        cols[2].metric("Total Events", summary.get("total_events"))

        extra = st.columns(2)
        extra[0].metric("Contagion Score", summary.get("contagion_score"))
        extra[1].metric("Panic Sells", summary.get("panic_sell_count"))


def _render_comparison_result(comparison: dict) -> None:
    runs = comparison.get("runs", []) or []
    if not runs:
        st.info("Nothing to compare.")
        return

    cols = st.columns(len(runs))
    for col, run in zip(cols, runs):
        col.markdown(f"**{run.get('scenario', 'Unknown scenario')}**")
        col.caption(run.get("replay_id", ""))
        for agent in run.get("agents", []) or []:
            grade = agent.get("grade", "—")
            color = GRADE_COLORS.get(grade, "#57606a")
            col.markdown(
                f"{_agent_label(agent.get('agent_id'))}: "
                f"<span style='background:{color};color:#ffffff;padding:1px 8px;"
                f"border-radius:5px;font-weight:600;'>{agent.get('score')} ({grade})</span>",
                unsafe_allow_html=True,
            )


def render_run_comparison() -> None:
    try:
        runs = api_client.list_replays()
    except requests.RequestException:
        st.info("Run history unavailable (backend unreachable).")
        return

    if not runs:
        st.caption("No past runs yet. Run a simulation to build history.")
        return

    # Most useful first: runs with the highest best-score on top.
    runs_sorted = sorted(
        runs,
        key=lambda r: r.get("best_score") if r.get("best_score") is not None else -1.0,
        reverse=True,
    )

    label_to_id: dict[str, str] = {}
    for run in runs_sorted:
        replay_id = run.get("replay_id")
        scenario = run.get("scenario") or "unknown"
        score = run.get("best_score")
        grade = run.get("best_grade") or "—"
        score_text = f"best {score} ({grade})" if score is not None else "no score"
        label_to_id[f"{scenario} · {score_text} · {replay_id}"] = replay_id

    selected_labels = st.multiselect(
        "Select runs to compare", options=list(label_to_id.keys())
    )
    selected_ids = [label_to_id[label] for label in selected_labels]

    if st.button("Compare", disabled=len(selected_ids) < 2):
        if len(selected_ids) < 2:
            st.warning("Select at least two runs to compare.")
            return
        try:
            comparison = api_client.compare_replays(selected_ids)
        except requests.HTTPError as exc:
            detail = exc.response.text if exc.response is not None else str(exc)
            st.error(f"Comparison failed: {detail}")
            return
        except requests.RequestException as exc:
            st.error(f"Comparison failed: {exc}")
            return
        _render_comparison_result(comparison)


def main() -> None:
    st.set_page_config(page_title="DUAT Arena", layout="wide")
    st.title("DUAT Arena")
    st.caption(
        "Stress testing for trading bots and AI agents — "
        "deterministic chaos scenarios, decision-integrity enforcement, explainable grades."
    )

    scenarios = load_scenarios()
    scenario_labels = {scenario["name"]: scenario["id"] for scenario in scenarios}

    agents = load_agents()
    # Map a display label -> agent id. Annotate kind so external agents stand out.
    agent_labels: dict[str, str] = {}
    for agent in agents:
        kind = agent.get("kind", "preset")
        label = f"{agent.get('name', agent.get('id'))} ({kind})"
        agent_labels[label] = agent.get("id")

    with st.sidebar:
        st.header("Controls")
        selected_name = st.selectbox("Scenario", list(scenario_labels.keys()))
        ticks = st.number_input("Ticks", min_value=5, max_value=200, value=30, step=1)

        selected_agent_ids: list[str] = []
        if agent_labels:
            selected_agent_labels = st.multiselect(
                "Agents",
                options=list(agent_labels.keys()),
                default=list(agent_labels.keys()),
                help="Choose which registered agents to run through the scenario.",
            )
            selected_agent_ids = [agent_labels[label] for label in selected_agent_labels]
        else:
            st.caption("Agent selection unavailable — running default presets.")

        run_clicked = st.button("Run Simulation", type="primary")

    if run_clicked:
        scenario_id = scenario_labels[selected_name]
        if agent_labels and not selected_agent_ids:
            st.warning("Select at least one agent to run.")
        else:
            try:
                with st.spinner("Running simulation..."):
                    summary = api_client.run_simulation(
                        scenario_id=scenario_id,
                        ticks=int(ticks),
                        agent_ids=selected_agent_ids or None,
                    )
                    replay = api_client.get_replay(summary["replay_id"])
                st.session_state["summary"] = summary
                st.session_state["events"] = replay.get("events", [])
            except requests.HTTPError as exc:
                detail = exc.response.text if exc.response is not None else str(exc)
                st.error(f"Simulation rejected by backend: {detail}")
            except requests.RequestException as exc:
                st.error(f"Simulation failed: {exc}")

    summary = st.session_state.get("summary")
    events = st.session_state.get("events", [])

    if summary:
        render_outcome_banner(summary)
        render_integrity_headline(summary, events)
        render_reliability_headline(summary)
        render_scorecards(summary, events)
        render_integrity_breakdown(summary, events)
        render_key_findings(summary)
        render_headline_metrics(summary)
        render_agent_outcomes(summary)
        render_key_events(events)
        render_timeline(events)
        render_agent_actions(events)
        render_market_details(summary)
    else:
        st.info("Choose a scenario and run a simulation to see results.")

    with st.expander("Compare Past Runs", expanded=False):
        render_run_comparison()


if __name__ == "__main__":
    main()
