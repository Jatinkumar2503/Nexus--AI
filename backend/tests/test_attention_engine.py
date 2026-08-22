"""Unit tests for Attention Management & Default Behavior Engine."""

import unittest
from backend.services.attention_engine import AttentionEngine

class TestAttentionEngine(unittest.TestCase):
    def setUp(self):
        self.engine = AttentionEngine()

    def test_calculate_crli_quiet_state(self):
        result = self.engine.calculate_crli(
            active_disruptions_count=1,
            pending_review_count=1,
            active_train_density=10,
            average_uncertainty_spread=0.5
        )
        self.assertIn("crli_score", result)
        self.assertEqual(result["load_state"], "QUIET")
        self.assertLess(result["crli_score"], 35.0)

    def test_calculate_crli_overload_state(self):
        result = self.engine.calculate_crli(
            active_disruptions_count=5,
            pending_review_count=8,
            active_train_density=20,
            average_uncertainty_spread=2.0
        )
        self.assertEqual(result["load_state"], "OVERLOAD")
        self.assertGreaterEqual(result["crli_score"], 75.0)

    def test_derive_context_defaults(self):
        input_state = {
            "current_delay_min": 20.0,
            "weather": "dense_fog",
            "train_priority": 5.0
        }
        res = self.engine.derive_context_defaults(input_state)
        self.assertIn("defaults", res)
        self.assertTrue(res["is_editable"])
        self.assertEqual(res["defaults"]["detour_route"], "FAST_LINE_BYPASS")
        self.assertEqual(res["defaults"]["recommended_platform"], "PF_2")
        self.assertEqual(res["defaults"]["target_speed_kmh"], 45.0)

    def test_triage_interruption_auto_approve(self):
        triage = self.engine.triage_interruption(
            event_type="MINOR_DELAY",
            model_confidence_pct=92.0,
            safety_violations_count=0,
            is_ood=False
        )
        self.assertEqual(triage["triage_category"], "QUIET_AUTO_EXECUTE")
        self.assertTrue(triage["is_auto_approved"])

    def test_triage_interruption_critical(self):
        triage = self.engine.triage_interruption(
            event_type="SIGNAL_FAILURE",
            model_confidence_pct=95.0,
            safety_violations_count=1,
            is_ood=True
        )
        self.assertEqual(triage["triage_category"], "IMMEDIATE_INTERRUPT")
        self.assertFalse(triage["is_auto_approved"])

    def test_update_settings(self):
        res = self.engine.update_settings({"auto_approve_confidence_threshold": 90.0})
        self.assertEqual(res["settings"]["auto_approve_confidence_threshold"], 90.0)

if __name__ == "__main__":
    unittest.main()
