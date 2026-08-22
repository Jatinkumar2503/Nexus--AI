"""Read-only operational intelligence tools for enhanced planning."""
from __future__ import annotations

from typing import Any, Dict, List

from simulation.engine import SimulationEngine

from .registry import ToolSpec

EMPTY_SCHEMA: Dict[str, Any] = {"type": "object", "properties": {}, "additionalProperties": False}


def crew_risk(engine: SimulationEngine) -> Dict[str, Any]:
    now = engine.get_sim_time_minutes()
    at_risk = [train["train_id"] for train in engine.get_active_trains() if train["crew_violated"]]
    return {"simulation_time_minutes": now, "at_risk_train_ids": at_risk, "violation_count": len(at_risk)}


def voltage_risk(engine: SimulationEngine) -> Dict[str, Any]:
    trains = engine.get_active_trains()
    affected = [{"train_id": train["train_id"], "voltage": train.get("voltage")} for train in trains if train.get("voltage") is not None and train["voltage"] < 24000]
    return {"threshold_volts": 24000, "affected_trains": affected, "affected_count": len(affected)}


def passenger_impact(engine: SimulationEngine) -> Dict[str, Any]:
    trains = engine.get_active_trains()
    impacted = [{"train_id": train["train_id"], "passengers": train["passenger_count"], "delay_minutes": train["delay_minutes"]} for train in trains if train["delay_minutes"] > 0]
    passenger_delay = sum(item["passengers"] * item["delay_minutes"] for item in impacted)
    return {"delayed_services": impacted, "passenger_delay_minutes": round(passenger_delay, 1)}


def disruption_risk(engine: SimulationEngine) -> Dict[str, Any]:
    now = engine.get_sim_time_minutes()
    active = [item for item in engine.disruptions if item["start_time"] <= now < item["start_time"] + item["duration"]]
    severities = {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}
    score = sum(severities.get(item.get("severity", ""), 2) * 25 for item in active)
    return {"active_disruptions": active, "risk_score": min(score, 100), "network_partition_risk": any(item.get("node_id") for item in active)}


def build_intelligence_tools(engine: SimulationEngine) -> List[ToolSpec]:
    return [
        ToolSpec("check_crew_risk", "Assess crew compliance and predicted roster violations.", lambda: crew_risk(engine), EMPTY_SCHEMA),
        ToolSpec("analyze_voltage_risk", "Assess low-voltage services and power safety risk.", lambda: voltage_risk(engine), EMPTY_SCHEMA),
        ToolSpec("estimate_passenger_impact", "Estimate passenger delay impact for delayed services.", lambda: passenger_impact(engine), EMPTY_SCHEMA),
        ToolSpec("analyze_disruption_risk", "Assess disruption severity, active incidents, and partition risk.", lambda: disruption_risk(engine), EMPTY_SCHEMA),
    ]
