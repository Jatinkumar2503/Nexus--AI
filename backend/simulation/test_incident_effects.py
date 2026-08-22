import unittest

from simulation.engine import SimulationEngine


class TestIncidentEffects(unittest.TestCase):
    def test_weather_is_a_speed_restriction_not_a_track_block(self):
        engine = SimulationEngine()
        engine.inject_disruption(
            node_id=None,
            edge_id="VAP->BIL",
            duration=60,
            severity="MEDIUM",
            description="Severe weather speed restriction and visibility check",
        )
        self.assertFalse(engine.is_track_blocked("VAP", "BIL"))
        self.assertEqual(engine.get_incident_speed_limit("VAP", "BIL"), 80.0)

    def test_maintenance_still_blocks_a_station_approach(self):
        engine = SimulationEngine()
        engine.inject_disruption(
            node_id="VAD",
            edge_id=None,
            duration=60,
            severity="MEDIUM",
            description="Planned maintenance window",
        )
        self.assertTrue(engine.is_track_blocked("BHA", "VAD"))

    def test_rolling_stock_failure_holds_nearby_train(self):
        engine = SimulationEngine()
        engine.inject_disruption("BHA", None, 60, "HIGH", "Rolling-stock failure requires rescue")
        self.assertTrue(any(train.status == "DELAYED" and train.delay_minutes >= 20 for train in engine.trains))

    def test_network_partition_enables_telemetry_safe_mode(self):
        engine = SimulationEngine()
        engine.inject_disruption("TNA", None, 60, "CRITICAL", "Control network partition isolates junction")
        self.assertTrue(any(train.telemetry_packet_lost for train in engine.trains))

    def test_cascading_incident_propagates_delay_and_voltage_guard(self):
        engine = SimulationEngine()
        engine.inject_disruption(None, "SUR->BHA", 60, "CRITICAL", "Cascading signal and traction incident")
        self.assertTrue(all(train.delay_minutes >= 5 for train in engine.trains))
        self.assertTrue(all(train.voltage <= 23500 for train in engine.trains))


if __name__ == "__main__":
    unittest.main()
