import json
import tempfile
import unittest
from pathlib import Path

from services.database import migrate_legacy_json
from services.plan_store import PlanStore
from services.recovery_memory import RecoveryMemory


class TestLegacyMigration(unittest.TestCase):
    def test_imports_json_plans_outcomes_and_preferences_once(self):
        record = {
            "id": "legacy-plan",
            "plan": {
                "recommended_strategy": "detour", "confidence_score": 0.8,
                "primary_reasoning": "legacy", "actions": [],
                "expected_metrics": {"delay_minutes": 1, "energy_kwh": 1, "crew_violations": 0, "resilience_score": 90},
            },
            "status": "proposed", "validation": None,
        }
        with tempfile.TemporaryDirectory() as directory:
            directory_path = Path(directory)
            plans_path = directory_path / "plans.json"
            memory_path = directory_path / "recovery_memory.json"
            database_path = directory_path / "nexus.db"
            plans_path.write_text(json.dumps([record]), encoding="utf-8")
            memory_path.write_text(json.dumps({"outcomes": [{"strategy": "detour"}], "preferences": {"replay_speed": 2}}), encoding="utf-8")

            migrate_legacy_json(database_path, plans_path, memory_path)
            migrate_legacy_json(database_path, plans_path, memory_path)

            self.assertEqual(PlanStore(database_path).get("legacy-plan").plan.recommended_strategy, "detour")
            self.assertEqual(RecoveryMemory(database_path).outcomes(), [{"strategy": "detour"}])
            self.assertEqual(RecoveryMemory(database_path).preferences(), {"replay_speed": 2})


if __name__ == "__main__":
    unittest.main()
