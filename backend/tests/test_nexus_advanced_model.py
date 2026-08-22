"""Unit Tests for Advanced NEXUS Neural Model Capabilities:
1. Scaling Ladder & Parameter Study
2. Epistemic Uncertainty & Mahalanobis OOD Detector
3. Direct Preference Optimization (DPO) Policy Alignment
4. Mechanistic Explainability & Attribution
5. Adversarial Stress & Telemetry Robustness
"""

import os
import sys
import unittest
import torch
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from models.nexus_core.nexus_model import build_nexus_model, NexusRailwayModel
from models.nexus_core.uncertainty_ood import UncertaintyAndOODDetector
from models.nexus_core.explainability import NexusExplainabilityEngine
from models.nexus_core.dpo_trainer import NexusDPOTrainer
from models.nexus_core.scaling_study import NexusScalingStudy, SCALING_TIERS
from models.nexus_core.stress_tester import NexusStressTester
from models.nexus_core.multi_agent_coordinator import MultiAgentDispatchCoordinator
from models.nexus_core.online_adapter import NexusOnlineAdapter
from models.nexus_core.model_export_jit import NexusModelOptimizer

class TestNexusAdvancedModel(unittest.TestCase):

    def setUp(self):
        self.model = build_nexus_model("fast_train")
        if os.path.exists("models/checkpoints/nexus_best.pt"):
            ckpt = torch.load("models/checkpoints/nexus_best.pt", map_location="cpu")
            self.model.load_state_dict(ckpt["model_state_dict"])
        self.model.eval()

    def test_scaling_study_architecture_ladder(self):
        study = NexusScalingStudy()
        tier_nano = study.profile_tier("nexus_nano", SCALING_TIERS["nexus_nano"], n_warmup=1, n_runs=3)
        self.assertGreater(tier_nano["trainable_parameters"], 1_000_000)
        self.assertLess(tier_nano["inference_latency_ms"]["p50"], 50.0)

    def test_uncertainty_and_ood_detection(self):
        detector = UncertaintyAndOODDetector(self.model)
        synthetic_ref = np.random.normal(loc=0.3, scale=0.15, size=(100, 7)).astype(np.float32)
        detector.fit_in_distribution_reference(synthetic_ref)

        in_dist_sample = synthetic_ref[0]
        res_in = detector.assess_safety_and_ood(in_dist_sample)
        self.assertFalse(res_in["is_out_of_distribution"])
        self.assertEqual(res_in["ood_status"], "IN_DISTRIBUTION_CONFIRMED")

        ood_sample = np.array([20.0, 10.0, 10.0, 0.0, 10.0, 0.0, 10.0], dtype=np.float32)
        res_ood = detector.assess_safety_and_ood(ood_sample)
        self.assertTrue(res_ood["is_out_of_distribution"])
        self.assertEqual(res_ood["ood_status"], "OOD_ANOMALY_DETECTED")

    def test_mechanistic_explainability(self):
        explainer = NexusExplainabilityEngine(self.model)
        feat = np.array([0.35, 1.0, 0.0, 0.9, 0.25, 0.65, 0.45], dtype=np.float32)
        explanation = explainer.explain_decision(feat, train_id="20901", station_id="SUR")
        
        self.assertIn("recommended_action", explanation)
        self.assertGreater(explanation["confidence_pct"], 50.0)
        self.assertGreater(len(explanation["top_attributing_features"]), 0)
        self.assertIn("contrastive_explanation", explanation)

    def test_dpo_loss_computation(self):
        trainer = NexusDPOTrainer(beta=0.1, lr=1e-4)
        b_X = torch.randn(4, 7)
        b_w = torch.tensor([4, 4, 3, 4], dtype=torch.int64) # winning actions
        b_l = torch.tensor([0, 1, 0, 1], dtype=torch.int64) # losing actions
        
        loss, metrics = trainer.compute_dpo_loss(b_X, b_w, b_l)
        self.assertGreater(loss.item(), 0.0)
        self.assertIn("preference_accuracy", metrics)
        self.assertIn("implicit_margin", metrics)

    def test_stress_adversarial_safety(self):
        tester = NexusStressTester()
        safety_results = tester.test_adversarial_safety_enforcement(n_adversarial_trials=20)
        self.assertEqual(safety_results["safety_rejection_rate_pct"], 100.0)
        self.assertEqual(safety_results["safety_invariant_violation_rate_pct"], 0.0)

    def test_multi_agent_coordination(self):
        coordinator = MultiAgentDispatchCoordinator()
        sector = [
            {"train_id": "VB-20901", "train_priority": 5.0, "location_station": "SUR", "current_delay_min": 5.0},
            {"train_id": "FR-90112", "train_priority": 2.0, "location_station": "SUR", "current_delay_min": 20.0}
        ]
        res = coordinator.coordinate_sector(sector)
        self.assertEqual(res["status"], "COORDINATED_OPTIMAL")
        self.assertEqual(len(res["dispatches"]), 2)
        self.assertTrue(res["joint_conflict_free"])

    def test_online_adapter(self):
        adapter = NexusOnlineAdapter()
        feat = np.array([0.2, 0.0, 0.0, 0.8, 0.25, 0.65, 0.5], dtype=np.float32)
        delays = np.array([5.0, 8.0, 12.0], dtype=np.float32)
        for _ in range(10):
            adapter.record_operational_telemetry(feat, delays, 4)
        step_res = adapter.adapt_step()
        self.assertEqual(step_res["status"], "ADAPTED")
        self.assertGreater(step_res["buffer_size"], 8)

    def test_jit_export(self):
        optimizer = NexusModelOptimizer()
        jit_path = optimizer.export_torchscript_jit("models/checkpoints/test_nexus_jit.pt")
        self.assertTrue(os.path.exists(jit_path))
        jit_model = torch.jit.load(jit_path)
        out = jit_model(torch.randn(1, 7))
        self.assertIn("action_logits", out)

if __name__ == "__main__":
    unittest.main()
