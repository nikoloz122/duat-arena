"""Single source of truth for chaos scenarios.

Both the API listing and the simulation runner select scenarios from here, so
scenario ids/names/descriptions are never duplicated across the codebase.
"""

from typing import Callable, Dict, List

from scenarios.base import ChaosScenario
from scenarios.flash_crash import FlashCrashScenario
from scenarios.liquidation_cascade import LiquidationCascadeScenario
from scenarios.liquidity_drain import LiquidityDrainScenario
from scenarios.oracle_failure import OracleFailureScenario
from scenarios.panic_contagion import PanicContagionScenario
from scenarios.stablecoin_depeg import StablecoinDepegScenario

ScenarioFactory = Callable[[], ChaosScenario]

DEFAULT_SCENARIO_ID = "flash-crash"

# Ordered registry of scenario_id -> factory.
_SCENARIO_FACTORIES: Dict[str, ScenarioFactory] = {
    FlashCrashScenario.id: FlashCrashScenario,
    LiquidityDrainScenario.id: LiquidityDrainScenario,
    PanicContagionScenario.id: PanicContagionScenario,
    OracleFailureScenario.id: OracleFailureScenario,
    StablecoinDepegScenario.id: StablecoinDepegScenario,
    LiquidationCascadeScenario.id: LiquidationCascadeScenario,
}


def scenario_ids() -> List[str]:
    return list(_SCENARIO_FACTORIES.keys())


def get_scenario(scenario_id: str) -> ChaosScenario:
    """Build a scenario by id, falling back to the default for unknown ids."""
    factory = _SCENARIO_FACTORIES.get(
        (scenario_id or "").lower(), _SCENARIO_FACTORIES[DEFAULT_SCENARIO_ID]
    )
    return factory()


def list_scenarios() -> List[Dict[str, str]]:
    """Return id, name, and description for every registered scenario."""
    listing: List[Dict[str, str]] = []
    for factory in _SCENARIO_FACTORIES.values():
        scenario = factory()
        listing.append(
            {
                "id": scenario.id,
                "name": scenario.name,
                "description": getattr(scenario, "description", ""),
            }
        )
    return listing
