import inspect
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from types import MappingProxyType
from typing import Any, Dict, List, Mapping, Tuple

from agents.base import AgentDecision, TradingAgent
from agents.llm_agent import LLM_AGENT_ID
from scenarios.base import ChaosScenario
from simulation.behavior import BehaviorTracker
from simulation.config import SimulationConfig
from simulation.decision_normalizer import normalize_decision
from simulation.events import ReplayEntry
from simulation.failure_analysis import analyze_agent
from simulation.manifest import AgentIdentity, SimulationManifest
from simulation.market import MarketState
from simulation.portfolio import ACTIVE, PortfolioState
from simulation.replay import ReplayRecorder
from simulation.scoring import score_agent


@dataclass
class SimulationResult:
    """Final result of a simulation run."""
    run_id: str
    replay_id: str
    ticks: int
    agents: List[str]
    scenario: str
    replay_path: str

    total_events: int
    panic_sell_count: int
    normal_sell_count: int
    surviving_agents: List[str]

    final_price: float
    final_liquidity: float
    final_volatility: float
    final_sentiment: float
    contagion_score: float

    agent_reports: List[Dict[str, Any]] = field(default_factory=list)
    failure_reports: List[Dict[str, Any]] = field(default_factory=list)
    reliability_reports: List[Dict[str, Any]] = field(default_factory=list)
    llm_tick0_diagnostics: Dict[str, Any] | None = None

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        if data.get("llm_tick0_diagnostics") is None:
            data.pop("llm_tick0_diagnostics", None)
        return data


def _serialize_raw_decision(raw: Any) -> Any:
    """JSON-safe view of whatever an agent.decide() returned."""
    if raw is None:
        return None
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, AgentDecision):
        return raw.to_dict()
    to_dict = getattr(raw, "to_dict", None)
    if callable(to_dict):
        return to_dict()
    return repr(raw)


class SimulationEngine:
    def __init__(
        self,
        agents: List[TradingAgent],
        scenario: ChaosScenario,
        max_ticks: int = 50,
        initial_market_state: MarketState | None = None,
        recorder: ReplayRecorder | None = None,
        config: SimulationConfig | None = None,
    ) -> None:
        if not agents:
            raise ValueError("At least one agent is required")

        self.agents = agents
        self.scenario = scenario
        self.max_ticks = max_ticks
        self.market_state = initial_market_state or MarketState()
        self.recorder = recorder if recorder is not None else ReplayRecorder()
        self.config = config or SimulationConfig()

        self.portfolios: Dict[str, PortfolioState] = {
            agent.id: PortfolioState(
                agent_id=agent.id,
                initial_cash=self.config.initial_cash,
                risk_config=self.config.risk,
            )
            for agent in self.agents
        }
        self.behavior_trackers: Dict[str, BehaviorTracker] = {
            agent.id: BehaviorTracker(agent.id) for agent in self.agents
        }

        # Seed each agent with a starting position so scenarios create
        # meaningful exposure, PnL, and drawdown.
        seed_price = self.market_state.current_price
        allocation_value = self.config.initial_allocation * self.config.initial_cash
        for portfolio in self.portfolios.values():
            portfolio.seed_position(seed_price, allocation_value)

        # Agents may optionally opt into a read-only portfolio snapshot by
        # declaring a `portfolio_snapshot` parameter. Preset agents do not, so
        # they keep their original signature and behavior unchanged.
        self._accepts_portfolio_snapshot: Dict[str, bool] = {}
        for agent in self.agents:
            try:
                params = inspect.signature(agent.decide).parameters
                self._accepts_portfolio_snapshot[agent.id] = "portfolio_snapshot" in params
            except (TypeError, ValueError):
                self._accepts_portfolio_snapshot[agent.id] = False

    def run(self) -> SimulationResult:
        """Run a full simulation with chaos scenario."""
        replay_id = self._generate_replay_id()

        panic_sell_count = 0
        normal_sell_count = 0

        # Count ticks per agent where the decision boundary had to intervene
        # (normalization or a recovered decide() error). Feeds decision_integrity.
        self._integrity_events: Dict[str, int] = {agent.id: 0 for agent in self.agents}
        llm_tick0_diagnostics: Dict[str, Any] | None = None

        for tick in range(self.max_ticks):
            self.market_state.advance_tick()

            scenario_event = self.scenario.apply(tick, self.market_state)
            scenario_payload = scenario_event.to_dict() if scenario_event else None

            for agent in self.agents:
                portfolio = self.portfolios[agent.id]
                tracker = self.behavior_trackers[agent.id]

                # Value the portfolio against the pre-trade market price.
                execution_price = self.market_state.current_price
                portfolio.update_market_price(execution_price)

                # The decision boundary: a faulty agent must never crash the
                # run or feed malformed values into the portfolio/market.
                decision, normalization_notes, decide_trace = self._decide_safely(
                    agent, tick, portfolio
                )
                if normalization_notes:
                    self._integrity_events[agent.id] += 1
                llm_decide_diagnostics = None
                if agent.id == LLM_AGENT_ID and tick == 0:
                    llm_decide_diagnostics = decide_trace
                    llm_tick0_diagnostics = decide_trace
                intended_action = decision.action

                # A failed/liquidated agent may not increase exposure.
                executed_action = intended_action
                if executed_action == "buy" and not portfolio.can_increase_exposure():
                    executed_action = "hold"

                if executed_action == "sell":
                    if self._is_panic_agent(agent):
                        panic_sell_count += 1
                    else:
                        normal_sell_count += 1

                # Apply the trade to the portfolio at the execution price, then
                # measure the agent's own exposure change (free of market drift).
                exposure_before = portfolio.exposure
                portfolio.apply_action(executed_action, price=execution_price, size=decision.size)
                exposure_after = portfolio.exposure
                tracker.record(executed_action, exposure_before, exposure_after)

                # Apply the action to the market, then re-value the portfolio.
                self.market_state.apply_agent_action(executed_action, size=decision.size)
                portfolio.update_market_price(self.market_state.current_price)

                self.recorder.record(
                    ReplayEntry(
                        timestamp=self._timestamp_for_tick(tick),
                        tick=tick,
                        agent=agent.id,
                        action=executed_action,
                        market_state=self.market_state.to_dict(),
                        scenario_event=scenario_payload,
                        reason=decision.reason,
                        metadata={
                            "action": decision.action,
                            "size": decision.size,
                            "reason": decision.reason,
                            "confidence": decision.confidence,
                            "agent_metadata": decision.metadata or {},
                        },
                        portfolio_state=portfolio.to_dict(),
                        behavior_counters=tracker.to_dict(),
                        intended_action=intended_action,
                        executed_action=executed_action,
                        normalization_notes=normalization_notes,
                        llm_decide_diagnostics=llm_decide_diagnostics,
                    )
                )

        manifest = self._build_manifest()
        replay_path = self.recorder.save(replay_id, manifest=manifest.to_dict())

        # Survival is defined solely by portfolio status, so it cannot conflict
        # with the per-agent status reported in agent_reports.
        surviving_agents = [
            agent.id for agent in self.agents
            if self.portfolios[agent.id].status == ACTIVE
        ]

        total_actions = self.max_ticks * len(self.agents)
        contagion_score = round(panic_sell_count / max(1, total_actions), 4)

        agent_reports = self._build_agent_reports()
        failure_results = [
            analyze_agent(report, self.config.risk) for report in agent_reports
        ]
        failure_reports = [result.to_dict() for result in failure_results]
        reliability_reports = [
            score_agent(report, failure_result, self.config.score).to_dict()
            for report, failure_result in zip(agent_reports, failure_results)
        ]

        result = SimulationResult(
            run_id=replay_id,
            replay_id=replay_id,
            ticks=self.max_ticks,
            agents=[agent.id for agent in self.agents],
            scenario=self.scenario.name,
            replay_path=str(replay_path),
            total_events=len(self.recorder.entries),
            panic_sell_count=panic_sell_count,
            normal_sell_count=normal_sell_count,
            surviving_agents=surviving_agents,
            final_price=self.market_state.current_price,
            final_liquidity=self.market_state.liquidity,
            final_volatility=self.market_state.volatility,
            final_sentiment=self.market_state.market_sentiment,
            contagion_score=contagion_score,
            agent_reports=agent_reports,
            failure_reports=failure_reports,
            reliability_reports=reliability_reports,
            llm_tick0_diagnostics=llm_tick0_diagnostics,
        )

        # Persist the full result as a sidecar so the run is reconstructable
        # from disk and comparable to other runs.
        self.recorder.save_summary(replay_id, result.to_dict())
        return result

    def _build_agent_reports(self) -> List[Dict[str, Any]]:
        reports: List[Dict[str, Any]] = []
        for agent in self.agents:
            report = self.portfolios[agent.id].to_dict()
            report["behavior_counters"] = self.behavior_trackers[agent.id].to_dict()
            # Decision-integrity facts feed the reliability score. total_decisions
            # equals one decision per tick for the whole run.
            report["decision_integrity_events"] = self._integrity_events.get(agent.id, 0)
            report["total_decisions"] = self.max_ticks
            reports.append(report)
        return reports

    def _decide_safely(
        self, agent: TradingAgent, tick: int, portfolio: PortfolioState
    ) -> Tuple[AgentDecision, List[str], Dict[str, Any]]:
        """Invoke an agent and return a canonical decision plus boundary notes.

        Never raises: a faulty agent falls back to a safe hold so the run
        continues deterministically. Also returns a diagnostic trace dict.
        """
        trace: Dict[str, Any] = {}
        try:
            if self._accepts_portfolio_snapshot.get(agent.id, False):
                raw = agent.decide(
                    tick=tick,
                    market_state=self.market_state,
                    portfolio_snapshot=self._portfolio_snapshot(portfolio),
                )
            else:
                raw = agent.decide(tick=tick, market_state=self.market_state)
        except Exception as exc:  # noqa: BLE001 - boundary must absorb any failure
            trace["raw_decision"] = None
            trace["exception_message"] = f"{type(exc).__name__}: {exc}"
            safe_hold = AgentDecision(
                action="hold", size=1.0, reason="", confidence=0.5, metadata={}
            )
            note = f"agent.decide raised {type(exc).__name__}: {exc}; defaulted to safe hold"
            trace["normalization_notes"] = [note]
            return safe_hold, [note], trace

        trace["raw_decision"] = _serialize_raw_decision(raw)
        llm_trace = getattr(agent, "llm_decide_diagnostics", None)
        if isinstance(llm_trace, dict) and llm_trace.get("tick") == tick:
            for key in (
                "cache_hit",
                "cache_miss",
                "anthropic_api_called",
                "parser_succeeded",
            ):
                if key in llm_trace:
                    trace[key] = llm_trace[key]
            internal_failure = llm_trace.get("internal_failure")
            if internal_failure:
                trace["exception_message"] = internal_failure

        result = normalize_decision(raw)
        trace["normalization_notes"] = list(result.notes)
        return result.decision, result.notes, trace

    def _portfolio_snapshot(self, portfolio: PortfolioState) -> Mapping[str, Any]:
        """Return a read-only view of the agent's portfolio at decision time."""
        return MappingProxyType(
            {
                "cash": portfolio.cash,
                "position": portfolio.position,
                "equity": portfolio.equity,
                "exposure": portfolio.exposure,
                "status": portfolio.status,
            }
        )

    def _build_manifest(self) -> SimulationManifest:
        agents = [
            AgentIdentity(
                id=agent.id,
                name=getattr(agent, "name", agent.id),
                risk_profile=getattr(agent, "risk_profile", "unknown"),
                is_panic_agent=bool(getattr(agent, "is_panic_agent", False)),
                agent_type=agent.__class__.__name__,
                agent_kind=getattr(agent, "agent_kind", "preset"),
                endpoint=getattr(agent, "endpoint", None),
            ).to_dict()
            for agent in self.agents
        ]
        return SimulationManifest(
            scenario_id=self.scenario.id,
            scenario_name=self.scenario.name,
            ticks=self.max_ticks,
            simulation_config={
                "initial_cash": self.config.initial_cash,
                "initial_allocation": self.config.initial_allocation,
                "risk": {
                    "liquidation_equity_ratio": self.config.risk.liquidation_equity_ratio,
                    "failure_drawdown_ratio": self.config.risk.failure_drawdown_ratio,
                },
                "score": self.config.score.weights(),
            },
            agents=agents,
        )

    def _is_panic_agent(self, agent: TradingAgent) -> bool:
        """Check if agent is a panic-type agent via the explicit agent contract."""
        return bool(getattr(agent, "is_panic_agent", False))

    def _timestamp_for_tick(self, tick: int) -> str:
        timestamp = datetime(2026, 1, 1, 9, 30, tick, tzinfo=UTC)
        return timestamp.isoformat()

    def _generate_replay_id(self) -> str:
        timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S-%f")
        return f"{self.scenario.id}-{self.max_ticks}t-{timestamp}"