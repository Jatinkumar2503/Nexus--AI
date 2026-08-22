"""Deterministic, read-only analytics exposed to the planning layer."""

from __future__ import annotations

from typing import Any, Dict, List

from simulation.engine import SimulationEngine, get_non_linear_delay

from .registry import ToolSpec


def get_operational_metrics(engine: SimulationEngine) -> Dict[str, Any]:
    """Summarize live operational impacts using the simulator's existing rules."""
    now = engine.get_sim_time_minutes()
    trains = engine.get_active_trains()
    priority_weights = {"Vande Bharat": 1.5, "Tejas Express": 1.2, "Local": 0.8}
    passenger_delay = sum(
        get_non_linear_delay(train["delay_minutes"])
        * train["passenger_count"]
        * priority_weights.get(train["service_type"], 1.0)
        for train in trains
    ) / 500.0
    energy = sum(train["energy_consumed_kwh"] for train in trains)
    crew_violations = sum(
        1
        for train in engine.trains
        if train.crew.check_violation(now, 0.0)
    )
    return {
        "simulation_time_minutes": now,
        "total_passenger_delay_minutes": round(passenger_delay, 1),
        "total_energy_kwh": round(energy, 1),
        "crew_violation_count": crew_violations,
    }


def build_analytics_tools(engine: SimulationEngine) -> List[ToolSpec]:
    """Build planner tool specifications for current operational metrics."""
    return [
        ToolSpec(
            name="get_operational_metrics",
            description="Get current passenger delay, energy use, and crew compliance metrics.",
            handler=lambda: get_operational_metrics(engine),
            input_schema={
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
        )
    ]
