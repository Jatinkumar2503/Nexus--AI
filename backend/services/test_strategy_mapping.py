"""Regression tests for planner-to-simulator strategy translation."""
import unittest

from services.strategy_mapping import simulation_strategy_for


class StrategyMappingTests(unittest.TestCase):
    def test_rich_planner_recommendations_have_safe_simulator_policies(self):
        expected = {
            "reroute": "detour",
            "reroute_and_prioritize": "detour",
            "mixed_strategy": "detour",
            "hold": "do_nothing",
            "crew_swap": "do_nothing",
            "inspection": "do_nothing",
        }
        for recommendation, executable in expected.items():
            with self.subTest(recommendation=recommendation):
                self.assertEqual(simulation_strategy_for(recommendation), executable)

    def test_unknown_strategy_is_rejected(self):
        with self.assertRaises(ValueError):
            simulation_strategy_for("unsafe_custom_strategy")
