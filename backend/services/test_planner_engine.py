"""Rule coverage for the deterministic local recovery engine."""
import unittest

from services.planner_engine import generate_recovery_plan
from simulation.models import Disruption, StationState, TrainState


def disruption(edge_id=None):
    return Disruption(id="D1", edge_id=edge_id, duration=30, severity="HIGH")


def train(**changes):
    values = {"train_id": "T1", "service_type": "Local", "direction": "UP", "current_node": "A", "next_node": "B", "speed_kmh": 60, "delay_minutes": 0, "passenger_count": 100, "coordinates": [0, 0], "energy_consumed_kwh": 20}
    values.update(changes)
    return TrainState(**values)


class PlannerEngineTests(unittest.TestCase):
    def plan(self, **changes):
        return generate_recovery_plan(disruption(changes.pop("edge_id", None)), [train(**changes)], [])

    def test_no_disruption_returns_do_nothing(self):
        result = self.plan()
        self.assertEqual(result.recommended_strategy, "do_nothing")
        self.assertEqual(result.confidence_score, 100)

    def test_blocked_edge_creates_detour(self):
        result = self.plan(edge_id="A->B")
        self.assertEqual(result.recommended_strategy, "reroute")
        self.assertIn("detour", [item.action_type for item in result.actions])

    def test_congested_station_holds_local(self):
        station = StationState(station_id="A", name="A", occupied_platforms=["1", "2", "3", "4", "5"], capacity=6, queue=[])
        result = generate_recovery_plan(disruption(), [train()], [station])
        self.assertIn("hold", [item.action_type for item in result.actions])

    def test_crew_violation_swaps_crew(self):
        self.assertIn("crew_swap", [item.action_type for item in self.plan(crew_violated=True).actions])

    def test_voltage_drop_reduces_speed_and_acceleration(self):
        actions = [item.action_type for item in self.plan(voltage=23000).actions]
        self.assertIn("reduce_acceleration", actions)
        self.assertIn("speed_throttle", actions)

    def test_telemetry_loss_dispatches_inspection(self):
        actions = [item.action_type for item in self.plan(telemetry_packet_lost=True).actions]
        self.assertIn("inspection", actions)
        self.assertIn("speed_throttle", actions)

    def test_passenger_overload_is_not_held(self):
        result = self.plan(passenger_count=1000)
        self.assertNotIn("hold", [item.action_type for item in result.actions])
        self.assertIn("priority_dispatch", [item.action_type for item in result.actions])

    def test_delay_prioritization_and_confidence(self):
        result = self.plan(delay_minutes=16)
        self.assertIn("priority_dispatch", [item.action_type for item in result.actions])
        self.assertEqual(result.confidence_score, 98)

    def test_multiple_conditions_generate_mixed_plan(self):
        result = self.plan(edge_id="A->B", delay_minutes=20, crew_violated=True, telemetry_packet_lost=True, voltage=23000)
        self.assertEqual(result.recommended_strategy, "reroute_and_prioritize")
        self.assertGreaterEqual(len(result.actions), 6)
