import tempfile
import unittest
from pathlib import Path
from services.recovery_memory import RecoveryMemory

class TestRecoveryMemory(unittest.TestCase):
    def test_persists_outcomes(self):
        with tempfile.TemporaryDirectory() as directory:
            memory = RecoveryMemory(Path(directory) / "nexus.db")
            memory.record_outcome({"strategy": "detour"})
            self.assertEqual(memory.outcomes(), [{"strategy": "detour"}])

if __name__ == "__main__":
    unittest.main()
