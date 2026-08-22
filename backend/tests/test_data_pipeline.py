"""Tests for NEXUS AI Data Foundation, Canonical Pipeline, and Knowledge Graph."""

import os
import sys
import unittest
import tempfile

# Ensure workspace root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from backend.data.schema import StationSchema, SectionSchema, CanonicalRailwayDataset, ProvenanceMetadata
from backend.data.ingestion.indian_railways_loader import load_canonical_railway_foundation
from backend.data.pipeline import RailwayDataPipeline
from backend.graph.railway_kg import RailwayKnowledgeGraph

class TestDataPipeline(unittest.TestCase):

    def test_canonical_ingestion(self):
        dataset = load_canonical_railway_foundation()
        self.assertIsInstance(dataset, CanonicalRailwayDataset)
        self.assertGreaterEqual(len(dataset.stations), 19)
        self.assertGreaterEqual(len(dataset.sections), 20)
        self.assertGreaterEqual(len(dataset.trains), 5)
        self.assertTrue(dataset.metadata.source_name.startswith("Indian Railways"))

    def test_pipeline_execution(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = os.path.join(tmp_dir, "canonical")
            pipeline = RailwayDataPipeline(output_dir=output_dir)
            dataset, report = pipeline.run_pipeline()

            self.assertEqual(report["status"], "SUCCESS")
            self.assertEqual(report["station_count"], len(dataset.stations))
            self.assertTrue(os.path.exists(report["output_path"]))
            self.assertTrue(os.path.exists(os.path.join(output_dir, "pipeline_audit_report.json")))

    def test_knowledge_graph_construction(self):
        dataset = load_canonical_railway_foundation()
        kg = RailwayKnowledgeGraph(dataset)

        # Validate node counts
        expected_nodes = len(dataset.stations) + len(dataset.platforms) + len(dataset.sections) + len(dataset.trains)
        self.assertEqual(kg.graph.number_of_nodes(), expected_nodes)

        # Validate topological invariants
        is_valid, errors = kg.validate_topological_invariants()
        self.assertTrue(is_valid, f"Topological invariant failures: {errors}")

        # Validate tensor export layout
        tensor_dict = kg.to_tensor_dict()
        self.assertIn("x_dict", tensor_dict)
        self.assertIn("edge_index_dict", tensor_dict)
        self.assertEqual(tensor_dict["x_dict"]["station"].shape, (len(dataset.stations), 10))
        self.assertEqual(tensor_dict["x_dict"]["section"].shape, (len(dataset.sections), 9))
        self.assertEqual(tensor_dict["x_dict"]["train"].shape, (len(dataset.trains), 11))
        self.assertEqual(tensor_dict["x_dict"]["platform"].shape, (len(dataset.platforms), 5))

    def test_dynamic_graph_updates(self):
        dataset = load_canonical_railway_foundation()
        kg = RailwayKnowledgeGraph(dataset)

        train_id = dataset.trains[0].train_number
        sec_id = dataset.sections[0].section_id

        # Update train occupancy
        kg.update_train_dynamic_state(
            train_number=train_id,
            current_sec=sec_id,
            current_plt=None,
            speed_kmh=110.0,
            delay_min=4.5
        )

        # Check occupancy edge exists
        has_occupancy = False
        for u, v, d in kg.graph.edges(train_id, data=True):
            if d.get("edge_type") == "occupies_sec" and v == sec_id:
                has_occupancy = True
                break
        self.assertTrue(has_occupancy, "Dynamic occupies_sec edge was not added.")

    def test_schema_rejection_on_invalid_data(self):
        with self.assertRaises(Exception):
            # Longitude out of valid range [-180, 180]
            StationSchema(
                station_id="INVALID",
                name="Invalid Station",
                division="Test",
                zone="Test",
                latitude=20.0,
                longitude=250.0,
                platform_count=2,
                is_junction=False,
                is_terminal=False,
                base_dwell_min=2.0
            )

if __name__ == "__main__":
    unittest.main(verbosity=2)
