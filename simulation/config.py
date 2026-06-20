from dataclasses import dataclass, field
from typing import Dict


@dataclass
class RiskConfig:
    """Configurable risk thresholds for portfolio failure/liquidation."""

    liquidation_equity_ratio: float = 0.6
    failure_drawdown_ratio: float = 0.4


@dataclass
class ScoreConfig:
    """Component weights for the DUAT reliability score. Must sum to 1.0.

    Kept isolated so scoring rules are configurable in one place rather than
    hardcoded across the scoring logic.
    """

    survival_weight: float = 0.30
    capital_preservation_weight: float = 0.25
    drawdown_control_weight: float = 0.20
    risk_discipline_weight: float = 0.15
    decision_integrity_weight: float = 0.10

    def weights(self) -> Dict[str, float]:
        return {
            "survival": self.survival_weight,
            "capital_preservation": self.capital_preservation_weight,
            "drawdown_control": self.drawdown_control_weight,
            "risk_discipline": self.risk_discipline_weight,
            "decision_integrity": self.decision_integrity_weight,
        }

    def validate(self) -> None:
        total = sum(self.weights().values())
        if abs(total - 1.0) > 1e-9:
            raise ValueError(f"ScoreConfig weights must sum to 1.0, got {total}")


@dataclass
class SimulationConfig:
    """Top-level simulation configuration. Owns risk and scoring config."""

    initial_cash: float = 1000.0
    # Fraction of initial cash each agent allocates to a starting position so
    # that scenarios produce meaningful exposure, PnL, and drawdown.
    initial_allocation: float = 0.5
    risk: RiskConfig = field(default_factory=RiskConfig)
    score: ScoreConfig = field(default_factory=ScoreConfig)
