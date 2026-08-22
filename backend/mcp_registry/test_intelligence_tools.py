import unittest

from mcp_registry.default_registry import build_default_registry
from simulation.engine import SimulationEngine


class IntelligenceToolTests(unittest.TestCase):
    def test_complete_read_only_intelligence_catalog_is_allowlisted(self):
        engine = SimulationEngine()
        registry = build_default_registry(engine, engine.topology)
        names = {item["name"] for item in registry.definitions()}
        self.assertTrue({"check_crew_risk", "analyze_voltage_risk", "estimate_passenger_impact", "analyze_disruption_risk"}.issubset(names))
        self.assertIn("violation_count", registry.execute("check_crew_risk", {}))
        with self.assertRaises(ValueError):
            registry.execute("unsafe_shell", {})
