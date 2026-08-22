"""Integration tests for the local planner HTTP gateway."""
import os
import sys
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

import main
from simulation.models import ValidationResult

REQUEST_BODY = {"disruption": {"id": "DIS-1", "edge_id": "MUM->TNA", "duration": 30, "severity": "HIGH"}, "trains": [], "stations": []}


class TestPlannerApi(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(main.app)

    def test_create_recovery_plan_is_available_without_configuration(self):
        response = self.client.post("/api/planner", json=REQUEST_BODY)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["recommended_strategy"], "reroute")
        self.assertFalse(response.json()["is_mock_response"])

    def test_planner_status_reports_local_engine(self):
        response = self.client.get("/api/planner/status")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["mode"], "local")

    @patch("main.ValidationAgent")
    def test_plan_lifecycle_requires_validation_before_approval(self, validator):
        validator.return_value.validate.return_value = ValidationResult(is_valid=True, validated_strategy="reroute", findings=[])
        created = self.client.post("/api/planner/plans", json=REQUEST_BODY).json()
        self.assertEqual(created["status"], "proposed")
        self.assertEqual(self.client.post(f"/api/planner/plans/{created['id']}/approve").status_code, 409)
        self.assertEqual(self.client.post(f"/api/planner/plans/{created['id']}/validate").json()["status"], "validated")
        self.assertEqual(self.client.post(f"/api/planner/plans/{created['id']}/approve").json()["status"], "approved")

    @patch("main.engine.resolve_scenario")
    @patch("main.ValidationAgent")
    def test_committing_reroute_plan_executes_simulator_detour(self, validator, resolve_scenario):
        validator.return_value.validate.return_value = ValidationResult(is_valid=True, validated_strategy="reroute", findings=[])
        created = self.client.post("/api/planner/plans", json=REQUEST_BODY).json()
        plan_id = created["id"]
        self.client.post(f"/api/planner/plans/{plan_id}/validate")
        self.client.post(f"/api/planner/plans/{plan_id}/approve")

        committed = self.client.post(f"/api/planner/plans/{plan_id}/commit")

        self.assertEqual(committed.status_code, 200)
        resolve_scenario.assert_called_once_with("detour")

    @patch("main.engine.resolve_scenario")
    @patch("main.ValidationAgent")
    def test_committed_plan_can_be_rolled_back_once(self, validator, resolve_scenario):
        validator.return_value.validate.return_value = ValidationResult(is_valid=True, validated_strategy="reroute", findings=[])
        plan_id = self.client.post("/api/planner/plans", json=REQUEST_BODY).json()["id"]
        self.client.post(f"/api/planner/plans/{plan_id}/validate")
        self.client.post(f"/api/planner/plans/{plan_id}/approve")
        self.client.post(f"/api/planner/plans/{plan_id}/commit")
        rollback = self.client.post(f"/api/planner/plans/{plan_id}/rollback")
        self.assertEqual(rollback.status_code, 200)
        self.assertEqual(rollback.json()["status"], "rolled_back")
        self.assertEqual(self.client.post(f"/api/planner/plans/{plan_id}/rollback").status_code, 409)

    def test_mutation_payloads_are_validated(self):
        invalid_disruption = self.client.post("/api/disruption/inject", json={"duration": 0, "description": "x"})
        invalid_telemetry = self.client.post("/api/simulation/telemetry", json={"axle_counter_id": "a", "train_id": "t", "timestamp": -1, "axle_count": -1, "event_type": "unknown"})
        self.assertEqual(invalid_disruption.status_code, 422)
        self.assertEqual(invalid_telemetry.status_code, 422)

    @patch.dict(os.environ, {"NEXUS_AUTH_REQUIRED": "true", "NEXUS_DISPATCHER_TOKEN": "test-token"})
    def test_protected_dispatcher_endpoints_require_valid_bearer_token(self):
        self.assertEqual(self.client.get("/api/audit-events").status_code, 401)
        self.assertEqual(self.client.get("/api/audit-events", headers={"Authorization": "Bearer test-token"}).status_code, 200)

    @patch.dict(os.environ, {"NEXUS_AUTH_REQUIRED": "true", "NEXUS_DISPATCHER_TOKEN": "test-token", "NEXUS_DISPATCHER_ROLE": "viewer"})
    def test_viewer_cannot_create_or_approve_recovery_plans(self):
        headers = {"Authorization": "Bearer test-token"}
        self.assertEqual(self.client.post("/api/planner/plans", json=REQUEST_BODY, headers=headers).status_code, 403)
        self.assertEqual(self.client.post("/api/disruption/inject", json={"edge_id": "MUM->TNA", "duration": 20, "severity": "HIGH", "description": "Role test"}, headers=headers).status_code, 403)

    @patch.dict(os.environ, {"NEXUS_AUTH_REQUIRED": "true", "NEXUS_DISPATCHER_TOKEN": "test-token"})
    def test_state_changing_preferences_and_telemetry_require_dispatcher_access(self):
        preferences = {"preferences": {"simulation_speed": 30}}
        telemetry = {"axle_counter_id": "AC-1", "train_id": "VB-20901", "timestamp": 1, "axle_count": 16, "event_type": "entry"}
        self.assertEqual(self.client.put("/api/memory/preferences", json=preferences).status_code, 401)
        self.assertEqual(self.client.post("/api/simulation/telemetry", json=telemetry).status_code, 401)
        headers = {"Authorization": "Bearer test-token"}
        self.assertEqual(self.client.put("/api/memory/preferences", json=preferences, headers=headers).status_code, 200)
        self.assertEqual(self.client.post("/api/simulation/telemetry", json=telemetry, headers=headers).status_code, 200)

    def test_health_check_confirms_storage(self):
        response = self.client.get("/healthz")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["storage"], "sqlite")
