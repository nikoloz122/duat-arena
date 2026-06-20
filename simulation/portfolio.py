from dataclasses import dataclass, field
from typing import Any, Dict

from simulation.config import RiskConfig

ACTIVE = "active"
FAILED = "failed"
LIQUIDATED = "liquidated"


@dataclass
class PortfolioState:
    """
    Financial state for a single agent. Long-only, MVP accounting.

    This object only tracks financial truth. It does not classify behavior,
    generate reports, or produce reliability scores.
    """

    agent_id: str
    initial_cash: float = 1000.0
    cash: float | None = None
    position: float = 0.0
    average_entry_price: float = 0.0
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    equity: float = 0.0
    exposure: float = 0.0
    max_drawdown: float = 0.0
    status: str = ACTIVE
    failure_reason: str | None = None
    risk_config: RiskConfig = field(default_factory=RiskConfig)

    _peak_equity: float = field(default=0.0, repr=False)

    def __post_init__(self) -> None:
        if self.cash is None:
            self.cash = self.initial_cash
        self.equity = round(self.cash + self.position * self.average_entry_price, 2)
        self._peak_equity = self.equity

    def can_increase_exposure(self) -> bool:
        return self.status == ACTIVE

    def apply_action(self, action: str, price: float, size: float = 1.0) -> None:
        """Apply a trade to the portfolio at the given execution price."""
        if action == "buy":
            self._buy(price, size)
        elif action in ("sell", "reduce_exposure"):
            self._sell(price, size)
        # "hold" and unknown actions do not change holdings.

        self._revalue(price)

    def update_market_price(self, price: float) -> None:
        """Re-value the portfolio against the current market price."""
        self._revalue(price)

    def seed_position(self, price: float, allocation_value: float) -> None:
        """Establish a starting position worth `allocation_value` at `price`.

        This is simulation setup, not an agent decision, so it is intentionally
        kept out of behavior tracking. It is equity-neutral at execution.
        """
        if price <= 0 or allocation_value <= 0:
            return

        units = allocation_value / price
        self._buy(price, units)
        self._revalue(price)
        # Re-anchor the drawdown peak to starting equity after seeding.
        self._peak_equity = max(self._peak_equity, self.equity)

    def _buy(self, price: float, size: float) -> None:
        if price <= 0 or size <= 0:
            return

        affordable_units = self.cash / price
        units = min(size, affordable_units)
        if units <= 0:
            return

        cost = units * price
        new_position = self.position + units
        self.average_entry_price = round(
            (self.average_entry_price * self.position + price * units) / new_position, 4
        )
        self.position = round(new_position, 6)
        self.cash = round(self.cash - cost, 2)

    def _sell(self, price: float, size: float) -> None:
        if price <= 0 or size <= 0 or self.position <= 0:
            return

        units = min(size, self.position)
        proceeds = units * price
        self.realized_pnl = round(
            self.realized_pnl + units * (price - self.average_entry_price), 2
        )
        self.cash = round(self.cash + proceeds, 2)
        self.position = round(self.position - units, 6)
        if self.position <= 0:
            self.position = 0.0
            self.average_entry_price = 0.0

    def _revalue(self, price: float) -> None:
        self.unrealized_pnl = round(self.position * (price - self.average_entry_price), 2)
        self.equity = round(self.cash + self.position * price, 2)
        self.exposure = round(self.position * price, 2)

        if self.equity > self._peak_equity:
            self._peak_equity = self.equity

        if self._peak_equity > 0:
            drawdown = (self._peak_equity - self.equity) / self._peak_equity
            self.max_drawdown = round(max(self.max_drawdown, drawdown), 4)

        self._update_status()

    def _update_status(self) -> None:
        if self.status != ACTIVE:
            return

        if self.equity <= self.initial_cash * self.risk_config.liquidation_equity_ratio:
            self.status = LIQUIDATED
            self.failure_reason = "Equity fell below liquidation threshold"
        elif self.max_drawdown >= self.risk_config.failure_drawdown_ratio:
            self.status = FAILED
            self.failure_reason = "Drawdown exceeded failure threshold"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "initial_cash": self.initial_cash,
            "cash": self.cash,
            "position": self.position,
            "average_entry_price": self.average_entry_price,
            "realized_pnl": self.realized_pnl,
            "unrealized_pnl": self.unrealized_pnl,
            "equity": self.equity,
            "exposure": self.exposure,
            "max_drawdown": self.max_drawdown,
            "status": self.status,
            "failure_reason": self.failure_reason,
        }
