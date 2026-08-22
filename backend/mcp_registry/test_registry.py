"""Unit tests for the planner tool allowlist and read-only adapters."""

import os
import sys
import unittest

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from mcp_registry import ToolRegistry, ToolRegistryError, ToolSpec, build_default_registry
from simulation.engine import SimulationEngine
from simulation.topology import RailTopology


class TestToolRegistry(unittest.TestCase):
    def test_registry_executes_only_registered_tools(self):
        registry = ToolRegistry()
        registry.register(
            ToolSpec("echo", "Return a supplied value.", lambda value: {"value": value}, {"type": "object"})
        )
        self.assertEqual(registry.execute("echo", {"value": "safe"}), {"value": "safe"})
        with self.assertRaises(ToolRegistryError):
            registry.execute("unknown", {})

    def test_duplicate_tool_names_are_rejected(self):
        registry = ToolRegistry()
        tool = ToolSpec("once", "A tool.", lambda: {}, {"type": "object"})
        registry.register(tool)
        with self.assertRaises(ToolRegistryError):
            registry.register(tool)

    def test_default_registry_exposes_expected_read_only_tools(self):
        engine = SimulationEngine()
        topology = RailTopology()
        registry = build_default_registry(engine, topology)
        names = {tool["name"] for tool in registry.definitions()}
        self.assertSetEqual(
            names,
            {
                "find_recovery_path",
                "get_active_disruptions",
                "get_network_topology",
                "get_operational_metrics",
                "get_simulation_snapshot",
                "compare_recovery_scenarios",
                "simulate_recovery_strategy",
                "check_crew_risk",
                "analyze_voltage_risk",
                "estimate_passenger_impact",
                "analyze_disruption_risk",
            },
        )

        path = registry.execute(
            "find_recovery_path",
            {"origin": "MUM", "destination": "TNA", "blocked_edges": []},
        )
        self.assertTrue(path["found"])
        self.assertEqual(path["path"], ["MUM", "TNA"])
        self.assertIsNone(engine.active_recovery_strategy)

    def test_scenario_tools_use_sandbox_without_mutating_live_engine(self):
        engine = SimulationEngine()
        engine.inject_disruption(None, "MUM->TNA", 30, "HIGH", "Test block")
        registry = build_default_registry(engine, RailTopology())
        before = list(engine.disruptions)
        comparison = registry.execute("compare_recovery_scenarios", {"monte_carlo_runs": 1})
        self.assertEqual(len(comparison["scenarios"]), 3)
        self.assertEqual(engine.disruptions, before)
        result = registry.execute("simulate_recovery_strategy", {"strategy": "detour", "monte_carlo_runs": 1})
        self.assertTrue(result["found"])
        self.assertEqual(result["scenario"]["id"], "detour")

    def test_scenario_tools_reject_unsupported_inputs(self):
        engine = SimulationEngine()
        engine.inject_disruption(None, "MUM->TNA", 30, "HIGH", "Test block")
        registry = build_default_registry(engine, RailTopology())
        with self.assertRaises(ValueError):
            registry.execute("simulate_recovery_strategy", {"strategy": "invented"})
        with self.assertRaises(ValueError):
            registry.execute("compare_recovery_scenarios", {"monte_carlo_runs": 0})


if __name__ == "__main__":
    unittest.main()
