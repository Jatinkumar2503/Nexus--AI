"""Deterministic recovery-plan validation against sandbox simulation evidence."""
from mcp_registry.scenario_tools import simulate_recovery_strategy
from agents.events import execution_events
from services.strategy_mapping import simulation_strategy_for
from simulation.engine import SimulationEngine
from simulation.models import ValidationFinding, ValidationRequest, ValidationResult

class ValidationAgent:
    def __init__(self, engine: SimulationEngine):
        self._engine = engine

    def validate(self, request: ValidationRequest) -> ValidationResult:
        strategy = request.plan.recommended_strategy
        execution_events.emit("validator", f"Validation started for {strategy}.")
        findings = []
        known_trains = {train.train_id for train in self._engine.trains}
        known_locations = set(self._engine.topology.graph.nodes)
        for action in request.plan.actions:
            if action.train_id not in known_trains:
                findings.append(ValidationFinding(code="unknown_train", severity="error", message=f"Action references unknown train {action.train_id}."))
            if action.location not in known_locations:
                findings.append(ValidationFinding(code="unknown_location", severity="error", message=f"Action references unknown location {action.location}."))
            if action.action_type == "detour" and not action.routing_path:
                findings.append(ValidationFinding(code="missing_route", severity="error", message="Detour action requires an explicit routing path."))
        if any(item.severity == "error" for item in findings):
            result = ValidationResult(is_valid=False, validated_strategy=strategy, findings=findings)
            execution_events.emit("validator", "Validation rejected ungrounded plan actions.")
            return result
        try:
            sandbox_strategy = simulation_strategy_for(strategy)
        except ValueError:
            findings.append(ValidationFinding(code="unsupported_strategy", severity="error", message="Plan uses an unsupported recovery strategy."))
            result = ValidationResult(is_valid=False, validated_strategy=strategy, findings=findings)
            execution_events.emit("validator", "Validation rejected unsupported strategy.")
            return result
        outcome = simulate_recovery_strategy(self._engine, sandbox_strategy, request.monte_carlo_runs)
        scenario = outcome["scenario"]
        if not scenario:
            findings.append(ValidationFinding(code="scenario_unavailable", severity="error", message="No sandbox scenario outcome is available."))
        elif not scenario["is_legal"]:
            findings.append(ValidationFinding(code="illegal_strategy", severity="error", message="Sandbox scenario violates hard operational constraints."))
        elif scenario["crew_violations_count"] > 0:
            findings.append(ValidationFinding(code="crew_violation", severity="error", message="Sandbox scenario has crew-compliance violations."))
        else:
            findings.append(ValidationFinding(code="validated", severity="info", message="Sandbox scenario satisfies current hard constraints."))
        result = ValidationResult(is_valid=not any(item.severity == "error" for item in findings), validated_strategy=strategy, findings=findings, scenario=scenario)
        execution_events.emit("validator", "Validation passed." if result.is_valid else "Validation found hard-constraint failures.")
        return result
