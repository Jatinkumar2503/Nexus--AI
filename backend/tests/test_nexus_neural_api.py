"""Tests for NEXUS Neural Inference and Benchmark API Endpoints."""

import os
import sys
import unittest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.main import app

class TestNexusNeuralApi(unittest.TestCase):

    def setUp(self):
        self.client = TestClient(app)

    def test_nexus_infer_endpoint(self):
        payload = {
            "train_id": "20901",
            "location_station": "SUR",
            "current_delay_min": 18.5,
            "weather": "dense_fog",
            "train_priority": 5.0,
            "platform_count": 6,
            "section_mps": 130.0,
            "hour_of_day": 8.5
        }
        # Warm up JIT/model weights
        _ = self.client.post("/api/nexus/infer", json=payload)
        
        # Test steady-state inference
        res = self.client.post("/api/nexus/infer", json=payload)
        self.assertEqual(res.status_code, 200)
        
        data = res.json()
        self.assertEqual(data["status"], "APPROVED")
        self.assertTrue(data["is_safety_approved"])
        self.assertEqual(len(data["safety_violations"]), 0)
        self.assertIn("recommended_action", data)
        self.assertGreater(data["confidence_pct"], 90.0)
        self.assertIn("predictions", data)
        self.assertIn("delay_15m_median", data["predictions"])
        self.assertIn("delay_15m_90pct_interval", data["predictions"])
        self.assertIn("causal_explanation", data)
        self.assertLess(data["performance"]["inference_latency_ms"], 50.0)

    def test_nexus_benchmarks_endpoint(self):
        res = self.client.get("/api/nexus/benchmarks")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("nexus_foundation_model", data)
        self.assertIn("baselines", data)
        self.assertEqual(data["nexus_foundation_model"]["safety_constraint_violations_pct"], 0.0)

    def test_nexus_multi_agent_coordinate_endpoint(self):
        payload = {
            "trains": [
                {"train_id": "VB-20901", "train_priority": 5.0, "location_station": "SUR", "current_delay_min": 5.0},
                {"train_id": "FR-90112", "train_priority": 2.0, "location_station": "SUR", "current_delay_min": 20.0}
            ]
        }
        res = self.client.post("/api/nexus/multi-agent-coordinate", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "COORDINATED_OPTIMAL")
        self.assertEqual(len(data["dispatches"]), 2)
        self.assertTrue(data["joint_conflict_free"])

    def test_nexus_attention_map_endpoint(self):
        res = self.client.get("/api/nexus/attention-map?corridor=western")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["corridor"], "WESTERN")
        self.assertIn("bottleneck_station", data)
        self.assertIn("station_rankings", data)

if __name__ == "__main__":
    unittest.main(verbosity=2)
