import unittest
import tempfile
from pathlib import Path
from services.plan_store import PlanStore
from simulation.models import PlanRecord, RecoveryPlan, ExpectedMetrics

class TestPlanStore(unittest.TestCase):
    def test_saves_and_retrieves_plan(self):
        plan = RecoveryPlan(recommended_strategy="detour", confidence_score=0.8, primary_reasoning="test", actions=[], expected_metrics=ExpectedMetrics(delay_minutes=1, energy_kwh=1, crew_violations=0, resilience_score=90))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "nexus.db"
            store = PlanStore(path); store.save(PlanRecord(id="plan-1", plan=plan))
            self.assertEqual(PlanStore(path).get("plan-1").status, "proposed")
            self.assertIsNone(store.get("missing"))

    def test_transition_rejects_stale_lifecycle_update(self):
        plan = RecoveryPlan(recommended_strategy="detour", confidence_score=0.8, primary_reasoning="test", actions=[], expected_metrics=ExpectedMetrics(delay_minutes=1, energy_kwh=1, crew_violations=0, resilience_score=90))
        with tempfile.TemporaryDirectory() as directory:
            store = PlanStore(Path(directory) / "nexus.db")
            store.save(PlanRecord(id="plan-1", plan=plan))
            self.assertEqual(store.transition("plan-1", "proposed", "validated").status, "validated")
            self.assertIsNone(store.transition("plan-1", "proposed", "rejected"))

if __name__ == "__main__":
    unittest.main()
