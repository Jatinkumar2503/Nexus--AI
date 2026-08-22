import unittest
import os
import sys

# Add backend directory to path if needed
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from simulation.models import (
    Disruption,
    TrainState,
    StationState,
    RecoveryAction,
    ExpectedMetrics,
    RecoveryPlan,
    PlannerRequest
)

class TestPlannerSchemas(unittest.TestCase):
    def test_recovery_action_validation(self):
        action_data = {
            "train_id": "VB-101",
            "action_type": "detour",
            "location": "SUR",
            "hold_duration_minutes": 10,
            "routing_path": ["MUM", "TNA", "SUR"]
        }
        action = RecoveryAction(**action_data)
        self.assertEqual(action.train_id, "VB-101")
        self.assertEqual(action.action_type, "detour")
        self.assertEqual(action.hold_duration_minutes, 10)
        self.assertEqual(action.routing_path, ["MUM", "TNA", "SUR"])

    def test_expected_metrics_validation(self):
        metrics_data = {
            "delay_minutes": 45.5,
            "energy_kwh": 350.0,
            "crew_violations": 1,
            "resilience_score": 75.0
        }
        metrics = ExpectedMetrics(**metrics_data)
        self.assertEqual(metrics.delay_minutes, 45.5)
        self.assertEqual(metrics.resilience_score, 75.0)

    def test_recovery_plan_validation(self):
        plan_data = {
            "recommended_strategy": "detour",
            "confidence_score": 0.95,
            "primary_reasoning": "Bypass signaling disruption at SUR node.",
            "actions": [
                {
                    "train_id": "VB-101",
                    "action_type": "detour",
                    "location": "SUR",
                    "hold_duration_minutes": 0,
                    "routing_path": ["MUM", "TNA", "SUR"]
                }
            ],
            "expected_metrics": {
                "delay_minutes": 20.0,
                "energy_kwh": 400.0,
                "crew_violations": 0,
                "resilience_score": 85.0
            }
        }
        plan = RecoveryPlan(**plan_data)
        self.assertEqual(plan.recommended_strategy, "detour")
        self.assertEqual(plan.expected_metrics.resilience_score, 85.0)
        self.assertEqual(len(plan.actions), 1)

    def test_planner_request_validation(self):
        request_data = {
            "disruption": {
                "id": "DIS-001",
                "node_id": "SUR",
                "duration": 60,
                "severity": "HIGH",
                "description": "Signal breakdown"
            },
            "trains": [
                {
                    "train_id": "VB-101",
                    "service_type": "EXPRESS",
                    "direction": "UP",
                    "current_node": "MUM",
                    "next_node": "TNA",
                    "speed_kmh": 120.0,
                    "delay_minutes": 5.0,
                    "passenger_count": 450,
                    "coordinates": [19.076, 72.877],
                    "status": "RUNNING",
                    "energy_consumed_kwh": 120.5
                }
            ],
            "stations": [
                {
                    "station_id": "MUM",
                    "name": "Mumbai Central",
                    "occupied_platforms": ["VB-101"],
                    "capacity": 4,
                    "queue": []
                }
            ]
        }
        request = PlannerRequest(**request_data)
        self.assertEqual(request.disruption.id, "DIS-001")
        self.assertEqual(request.trains[0].train_id, "VB-101")
        self.assertEqual(request.stations[0].station_id, "MUM")

if __name__ == "__main__":
    unittest.main()
