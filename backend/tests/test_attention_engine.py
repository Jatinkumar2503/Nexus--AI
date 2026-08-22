"""Comprehensive Unit Test Suite for Production Attention Engine."""

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
            average_uncertainty_spread=2.0,
            crew_expiration_warning_count=2
        )
        self.assertEqual(result["load_state"], "OVERLOAD")
        self.assertGreaterEqual(result["crli_score"], 75.0)

    def test_calculate_crli_weather_multiplier(self):
        res_std = self.engine.calculate_crli(2, 2, 10, 1.0, weather_condition="standard")
        res_fog = self.engine.calculate_crli(2, 2, 10, 1.0, weather_condition="dense_fog")
        self.assertGreater(res_fog["crli_score"], res_std["crli_score"])
        self.assertEqual(res_fog["breakdown"]["weather_multiplier"], 1.25)

    def test_derive_context_defaults_fog_and_high_priority(self):
        input_state = {
            "current_delay_min": 18.0,
            "weather": "dense_fog",
            "train_priority": 5.0,
            "train_class": "VANDE_BHARAT",
            "section_mps": 130.0
        }
        res = self.engine.derive_context_defaults(input_state)
        self.assertIn("defaults", res)
        self.assertTrue(res["is_editable"])
        self.assertEqual(res["defaults"]["detour_route"], "FAST_LINE_BYPASS")
        self.assertEqual(res["defaults"]["recommended_platform"], "PF_1 (Express Mainline)")
        self.assertEqual(res["defaults"]["target_speed_kmh"], 45.0)
        self.assertTrue(res["defaults"]["precedence_swap"])

    def test_triage_interruption_auto_approve(self):
        triage = self.engine.triage_interruption(
            event_type="MINOR_DELAY",
            model_confidence_pct=92.0,
            safety_violations_count=0,
            is_ood=False
        )
        self.assertEqual(triage["triage_category"], "QUIET_AUTO_EXECUTE")
        self.assertTrue(triage["is_auto_approved"])

    def test_triage_interruption_critical_safety_hazard(self):
        triage = self.engine.triage_interruption(
            event_type="SIGNAL_FAILURE",
            model_confidence_pct=95.0,
            safety_violations_count=1,
            is_ood=True
        )
        self.assertEqual(triage["triage_category"], "IMMEDIATE_INTERRUPT")
        self.assertFalse(triage["is_auto_approved"])
        self.assertEqual(triage["badge_color"], "RED")

    def test_triage_interruption_sensitivity_high(self):
        self.engine.update_settings({"interruption_sensitivity": "HIGH", "auto_approve_confidence_threshold": 85.0})
        # 88% confidence is below 85% + 5% = 90% threshold in HIGH sensitivity -> batch review
        triage = self.engine.triage_interruption("MINOR_DELAY", model_confidence_pct=88.0)
        self.assertEqual(triage["triage_category"], "BATCH_REVIEW")

    def test_dispatcher_learning_memory(self):
        self.engine.record_dispatcher_decision("REC-100", accepted=True)
        stats = self.engine.get_dispatcher_acceptance_stats()
        self.assertGreater(stats["total_decisions"], 0)
        self.assertGreaterEqual(stats["acceptance_rate_pct"], 0.0)

    def test_update_settings_bounds_validation(self):
        # Test lower bound clamp
        res = self.engine.update_settings({"auto_approve_confidence_threshold": 20.0})
        self.assertEqual(res["settings"]["auto_approve_confidence_threshold"], 50.0)

        # Test upper bound clamp
        res = self.engine.update_settings({"auto_approve_confidence_threshold": 120.0})
        self.assertEqual(res["settings"]["auto_approve_confidence_threshold"], 99.0)

if __name__ == "__main__":
    unittest.main()
