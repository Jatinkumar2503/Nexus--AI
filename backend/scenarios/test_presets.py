import unittest
from scenarios import PRESETS

class TestScenarioPresets(unittest.TestCase):
    def test_required_demo_presets_exist(self):
        self.assertSetEqual(set(PRESETS), {
            "signal_failure", "monsoon_washout", "substation_failure",
            "severe_weather", "maintenance_window", "rolling_stock_failure",
            "network_partition", "cascading_incident",
        })
        for preset in PRESETS.values():
            self.assertTrue(preset.get("edge_id") or preset.get("node_id"))
            self.assertGreater(preset["duration"], 0)

if __name__ == "__main__":
    unittest.main()
