"""Read-only views over the active SimPy simulation."""

from __future__ import annotations

from typing import Any, Dict, List

from simulation.engine import SimulationEngine

from .registry import ToolSpec


def get_simulation_snapshot(engine: SimulationEngine) -> Dict[str, Any]:
    """Return the current simulation state without advancing or mutating it."""
    return {
        "simulation_time": engine.get_sim_time_str(),
        "trains": engine.get_active_trains(),
        "active_disruptions": list(engine.disruptions),
        "active_recovery_strategy": engine.active_recovery_strategy,
    }


def get_active_disruptions(engine: SimulationEngine) -> Dict[str, Any]:
    """Return disruptions that are active at the current simulation time."""
    now = engine.get_sim_time_minutes()
    active = [
        disruption
        for disruption in engine.disruptions
        if disruption["start_time"] <= now < disruption["start_time"] + disruption["duration"]
    ]
    return {"simulation_time_minutes": now, "disruptions": active}


def build_simulation_tools(engine: SimulationEngine) -> List[ToolSpec]:
    """Build planner tool specifications bound to the active simulator."""
    empty_schema: Dict[str, Any] = {
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    }
    return [
        ToolSpec(
            name="get_simulation_snapshot",
            description="Get train, disruption, and recovery state from the live simulator.",
            handler=lambda: get_simulation_snapshot(engine),
            input_schema=empty_schema,
        ),
        ToolSpec(
            name="get_active_disruptions",
            description="Get disruptions active at the current simulation time.",
            handler=lambda: get_active_disruptions(engine),
            input_schema=empty_schema,
        ),
    ]
