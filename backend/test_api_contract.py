"""Submission contract: every documented public endpoint remains present in OpenAPI."""
import unittest
from fastapi.testclient import TestClient

import main


class TestApiContract(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(main.app)

    def test_openapi_lists_every_submission_endpoint(self):
        paths = self.client.get("/openapi.json").json()["paths"]
        expected = {
            "/", "/healthz", "/api/health", "/api/topology", "/api/live-trains", "/api/simulation/state",
            "/api/simulation/control", "/api/disruption/inject", "/api/scenarios/compare", "/api/scenarios/resolve",
            "/api/scenarios/approve", "/api/memory/outcomes", "/api/memory/preferences", "/api/scenarios/presets",
            "/api/scenarios/presets/{preset_name}/inject", "/api/planner", "/api/planner/status", "/api/planner/plans",
            "/api/planner/plans/{plan_id}", "/api/planner/plans/{plan_id}/validate", "/api/planner/plans/{plan_id}/approve",
            "/api/planner/plans/{plan_id}/commit", "/api/planner/plans/{plan_id}/rollback", "/api/audit-events", "/api/planner/validate",
            "/api/scenarios/{strategy}/explain", "/api/scenarios/why-not", "/api/scenarios/{strategy}/confidence",
            "/api/planner/events", "/api/replay/timeline", "/api/simulation/telemetry",
        }
        self.assertTrue(expected.issubset(paths), expected - set(paths))

    def test_read_only_operational_endpoints_return_success(self):
        for path in ("/", "/healthz", "/api/health", "/api/topology", "/api/live-trains", "/api/simulation/state", "/api/memory/outcomes", "/api/memory/preferences", "/api/scenarios/presets", "/api/planner/status", "/api/replay/timeline"):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 200)

    def test_api_applies_security_headers(self):
        response = self.client.get("/api/health")
        self.assertEqual(response.headers["x-content-type-options"], "nosniff")
        self.assertEqual(response.headers["x-frame-options"], "DENY")
        self.assertEqual(response.headers["referrer-policy"], "no-referrer")

    def test_expensive_planner_routes_are_rate_limited(self):
        previous_limit = main.RATE_LIMIT_REQUESTS
        main._request_windows.clear()
        main.RATE_LIMIT_REQUESTS = 1
        try:
            self.assertEqual(self.client.post("/api/planner", json={
                "disruption": {"id": "rate-limit", "edge_id": "MUM->TNA", "duration": 20, "severity": "HIGH"},
                "trains": [], "stations": [],
            }).status_code, 200)
            limited = self.client.post("/api/planner", json={
                "disruption": {"id": "rate-limit", "edge_id": "MUM->TNA", "duration": 20, "severity": "HIGH"},
                "trains": [], "stations": [],
            })
            self.assertEqual(limited.status_code, 429)
            self.assertEqual(limited.headers["content-type"], "application/problem+json")
        finally:
            main.RATE_LIMIT_REQUESTS = previous_limit
            main._request_windows.clear()

    def test_simulation_and_decision_endpoints_complete_dispatcher_flow(self):
        self.assertEqual(self.client.post("/api/simulation/control", json={"action": "reset", "speed": 30}).status_code, 200)
        self.assertEqual(self.client.post("/api/simulation/control", json={"action": "pause"}).status_code, 200)
        self.assertEqual(self.client.post("/api/simulation/control", json={"action": "play", "speed": 60}).status_code, 200)
        self.assertEqual(self.client.put("/api/memory/preferences", json={"preferences": {"simulation_speed": 60}}).status_code, 200)

        disruption = self.client.post("/api/disruption/inject", json={
            "edge_id": "MUM->TNA", "duration": 30, "severity": "HIGH", "description": "Contract-test signal failure"
        })
        self.assertEqual(disruption.status_code, 200)

        scenarios = self.client.get("/api/scenarios/compare").json()["scenarios"]
        self.assertTrue(scenarios)
        self.assertEqual(self.client.post("/api/scenarios/approve", json={"strategy": "detour"}).status_code, 200)
        self.assertEqual(self.client.post("/api/scenarios/resolve", json={"strategy": "detour"}).status_code, 200)

        self.assertEqual(self.client.get("/api/scenarios/detour/explain").status_code, 200)
        self.assertEqual(self.client.get("/api/scenarios/detour/confidence").status_code, 200)
        self.assertEqual(self.client.post("/api/scenarios/why-not", json={"strategy": "short_turn"}).status_code, 200)
        self.assertEqual(self.client.post("/api/simulation/telemetry", json={
            "axle_counter_id": "AC-1", "train_id": "VB-20901", "timestamp": 1.0, "axle_count": 16, "event_type": "entry"
        }).status_code, 200)

    def test_missing_resources_have_meaningful_http_statuses(self):
        self.assertEqual(self.client.get("/api/planner/plans/does-not-exist").status_code, 404)
        self.assertEqual(self.client.post("/api/scenarios/presets/does-not-exist/inject").status_code, 404)
        self.assertEqual(self.client.get("/api/scenarios/not-a-strategy/explain").status_code, 404)


if __name__ == "__main__":
    unittest.main()
