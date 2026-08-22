"""Tests for Phase 3: Calibrated Simulation Engine and Deterministic Safety Validator."""

import os
import sys
import unittest
import tempfile

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from backend.data.ingestion.indian_railways_loader import load_canonical_railway_foundation
from backend.constraints.validator import DeterministicSafetyValidator
from backend.simulation.calibrated_engine import CalibratedSimulationEngine
from backend.simulation.calibration import DistributionCalibrator

class TestPhase3SimulationAndConstraints(unittest.TestCase):

    def setUp(self):
        self.dataset = load_canonical_railway_foundation()
        self.validator = DeterministicSafetyValidator(self.dataset)

    def test_temporal_sequencing_validation(self):
        # Valid dwell
        is_valid, err = self.validator.check_temporal_sequencing("20901", arrival_min=10.0, departure_min=15.0, station_id="MUM")
        self.assertTrue(is_valid)
        self.assertIsNone(err)

        # Invalid negative dwell
        is_valid, err = self.validator.check_temporal_sequencing("20901", arrival_min=15.0, departure_min=10.0, station_id="MUM")
        self.assertFalse(is_valid)
        self.assertIn("Negative dwell time", err)

    def test_platform_clearance_validation(self):
        # Valid berthing
        is_valid, err = self.validator.check_platform_clearance("20901", "MUM_PF1", active_occupant=None)
        self.assertTrue(is_valid)

        # Rejection on platform already occupied
        is_valid, err = self.validator.check_platform_clearance("20901", "MUM_PF1", active_occupant="12951")
        self.assertFalse(is_valid)
        self.assertIn("already occupied", err)

    def test_speed_compliance_validation(self):
        sec_id = self.dataset.sections[0].section_id
        # Valid speed
        is_valid, err = self.validator.check_speed_compliance("20901", sec_id, proposed_speed_kmh=100.0)
        self.assertTrue(is_valid)

        # Rejection on overspeed
        is_valid, err = self.validator.check_speed_compliance("20901", sec_id, proposed_speed_kmh=220.0)
        self.assertFalse(is_valid)
        self.assertIn("overspeed violation", err)

    def test_calibrated_simulation_run(self):
        engine = CalibratedSimulationEngine(self.dataset, random_seed=42)
        results = engine.run_simulation(duration_minutes=900.0)

        self.assertGreater(results["total_stops_executed"], 0)
        self.assertGreaterEqual(results["train_completion_rate"], 0.8)
        self.assertIn("mean_delay_minutes", results)
        self.assertIn("mean_dwell_minutes", results)

    def test_distribution_calibrator(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            calibrator = DistributionCalibrator(output_dir=tmp_dir)
            report = calibrator.run_calibration()

            self.assertIn("status", report)
            self.assertIn("kolmogorov_smirnov_pvalue", report["metrics"])
            self.assertIn("wasserstein_distance", report["metrics"])
            self.assertTrue(os.path.exists(os.path.join(tmp_dir, "calibration_report.json")))

if __name__ == "__main__":
    unittest.main(verbosity=2)
