"""Sandbox scenario tools for Milestone 2 planning."""
from typing import Any, Dict, List
from simulation.engine import SimulationEngine
from .registry import ToolSpec

STRATEGIES = ("do_nothing", "detour", "short_turn")

def compare_recovery_scenarios(engine: SimulationEngine, monte_carlo_runs: int = 3) -> Dict[str, Any]:
    """Run cloned simulations; never changes the live engine state."""
    if not 1 <= monte_carlo_runs <= 10:
        raise ValueError("monte_carlo_runs must be between 1 and 10.")
    strategy_before = engine.active_recovery_strategy
    disruptions_before = list(engine.disruptions)
    scenarios = engine.evaluate_scenarios(num_mc_runs=monte_carlo_runs)
    if engine.active_recovery_strategy != strategy_before or engine.disruptions != disruptions_before:
        raise RuntimeError("Scenario sandbox attempted to mutate live simulation state.")
    return {"monte_carlo_runs": monte_carlo_runs, "scenarios": scenarios}

def simulate_recovery_strategy(engine: SimulationEngine, strategy: str, monte_carlo_runs: int = 3) -> Dict[str, Any]:
    """Return the sandbox outcome for one supported recovery strategy."""
    if strategy not in STRATEGIES:
        raise ValueError(f"Unsupported recovery strategy: {strategy}")
    comparison = compare_recovery_scenarios(engine, monte_carlo_runs)
    scenario = next((item for item in comparison["scenarios"] if item["id"] == strategy), None)
    return {"strategy": strategy, "scenario": scenario, "found": scenario is not None}

def build_scenario_tools(engine: SimulationEngine) -> List[ToolSpec]:
    return [
        ToolSpec("compare_recovery_scenarios", "Compare sandboxed recovery strategies.", lambda monte_carlo_runs=3: compare_recovery_scenarios(engine, monte_carlo_runs), {"type":"object","properties":{"monte_carlo_runs":{"type":"integer","minimum":1,"maximum":10}},"additionalProperties":False}),
        ToolSpec("simulate_recovery_strategy", "Simulate one recovery strategy in a sandbox.", lambda strategy, monte_carlo_runs=3: simulate_recovery_strategy(engine, strategy, monte_carlo_runs), {"type":"object","properties":{"strategy":{"type":"string","enum":list(STRATEGIES)},"monte_carlo_runs":{"type":"integer","minimum":1,"maximum":10}},"required":["strategy"],"additionalProperties":False}),
    ]
