"""Deterministic, local recovery planning for the railway simulator."""

from __future__ import annotations

from typing import Iterable

from simulation.models import Disruption, ExpectedMetrics, RecoveryAction, RecoveryPlan, StationState, StrategyAlternative, TrainState


SERVICE_PRIORITY = {"vande bharat": 0, "tejas": 1, "express": 2, "freight": 3, "local": 4}


def _priority(train: TrainState) -> int:
    service = train.service_type.strip().lower()
    return next((value for name, value in SERVICE_PRIORITY.items() if name in service), len(SERVICE_PRIORITY))


def _ordered(trains: Iterable[TrainState]) -> list[TrainState]:
    return sorted(trains, key=lambda train: (_priority(train), -train.delay_minutes, -train.passenger_count))


def _action(train: TrainState, action_type: str, rationale: str, *, hold: int = 0, path: list[str] | None = None) -> RecoveryAction:
    return RecoveryAction(
        train_id=train.train_id,
        action_type=action_type,
        location=train.current_node,
        hold_duration_minutes=hold,
        routing_path=path,
        rationale=rationale,
    )


def _detour_path(edge_id: str) -> list[str]:
    parts = [item.strip() for item in edge_id.replace("-", "->").split("->") if item.strip()]
    if len(parts) >= 2:
        return [parts[0], f"{parts[0]}_SWITCH", f"{parts[-1]}_SWITCH", parts[-1]]
    return ["NEAREST_SWITCH_LINE"]


def _strategy(has_disruption: bool, action_types: set[str]) -> str:
    if not has_disruption and not action_types:
        return "do_nothing"
    if has_disruption and not action_types:
        return "reroute"
    if action_types == {"crew_swap"}:
        return "crew_swap"
    if action_types.issubset({"speed_throttle", "reduce_acceleration", "inspection"}):
        return "inspection"
    if action_types == {"hold"}:
        return "hold"
    if "detour" in action_types and "priority_dispatch" in action_types:
        return "reroute_and_prioritize"
    if action_types == {"detour"}:
        return "reroute"
    return "mixed_strategy"


def generate_recovery_plan(disruption: Disruption, trains: list[TrainState], stations: list[StationState]) -> RecoveryPlan:
    """Create an auditable recovery plan without network or model dependencies."""
    actions: list[RecoveryAction] = []
    reasons: list[str] = []
    ordered_trains = _ordered(trains)
    has_disruption = bool(disruption.edge_id or disruption.node_id)
    congested = {
        station.station_id
        for station in stations
        if station.capacity > 0 and len(station.occupied_platforms) / station.capacity > 0.8
    }

    if disruption.edge_id:
        path = _detour_path(disruption.edge_id)
        for train in ordered_trains:
            actions.append(_action(train, "detour", f"Blocked edge {disruption.edge_id}; divert via the nearest switch line.", path=path))
        reasons.append(f"Blocked edge {disruption.edge_id} requires a switch-line detour.")

    local_holds = [
        train for train in reversed(ordered_trains)
        if _priority(train) == SERVICE_PRIORITY["local"]
        and train.passenger_count <= 900
        and (train.current_node in congested or train.next_node in congested)
    ]
    for train in local_holds:
        actions.append(_action(train, "hold", "Platform occupancy exceeds 80%; hold Local service before higher-priority trains.", hold=10))
    if local_holds:
        reasons.append("Congested platforms are protected by holding eligible Local services first.")

    for train in ordered_trains:
        if train.delay_minutes > 15:
            actions.append(_action(train, "priority_dispatch", "Delay exceeds 15 minutes; increase scheduling priority."))
        if train.passenger_count > 900 and not disruption.edge_id:
            actions.append(_action(train, "priority_dispatch", "Passenger load exceeds 900; avoid holding and prioritize movement."))
        if train.crew_violated:
            actions.append(_action(train, "crew_swap", "Crew-duty limit is violated; arrange a crew swap."))
        if train.telemetry_packet_lost:
            actions.append(_action(train, "speed_throttle", "Telemetry packet loss detected; reduce speed."))
            actions.append(_action(train, "inspection", "Telemetry packet loss detected; dispatch inspection."))
        if train.voltage is not None and train.voltage < 24000:
            actions.append(_action(train, "reduce_acceleration", "Voltage is below 24 kV; reduce acceleration."))
            actions.append(_action(train, "speed_throttle", "Voltage is below 24 kV; reduce speed."))

    if not has_disruption and not actions:
        reasons.append("No active disruption or operating-rule exception was detected.")
    elif not reasons:
        reasons.append("Local operating rules detected service conditions requiring intervention.")

    delayed = sum(train.delay_minutes > 15 for train in trains)
    crew_violations = sum(train.crew_violated for train in trains)
    confidence = max(0, min(100, 100 - 5 * int(has_disruption) - 2 * delayed - 3 * crew_violations))
    detours = sum(action.action_type == "detour" for action in actions)
    holds = sum(action.action_type == "hold" for action in actions)
    speed_restrictions = sum(action.action_type == "speed_throttle" for action in actions)
    delay = sum(max(0, train.delay_minutes) for train in trains) + 12 * detours + 10 * holds
    energy = round(sum(max(0, train.energy_consumed_kwh) for train in trains) + 25 * detours + 4 * speed_restrictions, 2)
    remaining_crew = max(0, crew_violations - sum(action.action_type == "crew_swap" for action in actions))
    resilience = max(0, min(100, round(100 - delay * 0.2 - detours * 3 - remaining_crew * 8, 2)))
    return RecoveryPlan(
        recommended_strategy=_strategy(has_disruption, {action.action_type for action in actions}),
        confidence_score=float(confidence),
        primary_reasoning=" ".join(reasons),
        actions=actions,
        expected_metrics=ExpectedMetrics(delay_minutes=round(delay, 2), energy_kwh=energy, crew_violations=remaining_crew, resilience_score=float(resilience)),
        is_mock_response=False,
        alternative_strategies=[
            StrategyAlternative(strategy="do_nothing", rationale="Preserves the timetable but accepts disruption impact.", tradeoff="Lowest operational intervention; highest delay exposure.", rank=2),
            StrategyAlternative(strategy="short_turn", rationale="Turns affected services at the nearest operational boundary.", tradeoff="Reduces network blockage but disrupts passenger journeys.", rank=3),
        ],
        risk_factors=[item for item in [
            "Blocked track segment" if disruption.edge_id else None,
            "Crew compliance risk" if crew_violations else None,
            "High passenger load" if any(train.passenger_count > 900 for train in trains) else None,
            "Telemetry or voltage degradation" if any(train.telemetry_packet_lost or (train.voltage is not None and train.voltage < 24000) for train in trains) else None,
        ] if item],
        assumptions=["Topology and train snapshots represent the current operational state.", "Dispatcher approval is required before any recovery commit."],
        uncertainties=["Actual dwell and passenger-transfer times may vary.", "Future disruptions are not included in this estimate."],
        recovery_timeline_minutes=[0, 10, 30],
    )
