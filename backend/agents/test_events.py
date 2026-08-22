import unittest
import tempfile
from pathlib import Path
from agents.events import ExecutionEventStore

class TestExecutionEventStore(unittest.TestCase):
    def test_reads_events_after_cursor(self):
        store = ExecutionEventStore()
        first = store.emit("planner", "started")
        second = store.emit("tool", "queried")
        self.assertEqual(store.after(first["id"])[-1]["message"], second["message"])

    def test_persists_events_for_replay_after_new_store(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "events.db"
            first = ExecutionEventStore()
            first.configure_persistence(database)
            event = first.emit("planner", "durable event")
            replay = ExecutionEventStore()
            replay.configure_persistence(database)
            self.assertEqual(replay.after(None)[0]["id"], event["id"])
            self.assertEqual(replay.after(None)[0]["message"], "durable event")

if __name__ == "__main__":
    unittest.main()
