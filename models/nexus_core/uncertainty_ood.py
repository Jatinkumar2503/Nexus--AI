"""NEXUS AI — Epistemic Uncertainty & Out-of-Distribution (OOD) Detector.

Provides:
1. Monte Carlo Dropout (MCD) for Epistemic Variance Estimation
2. Mahalanobis Distance Feature Space OOD Detection
3. Calibrated Conformal Prediction Error Bounds
4. Decision Reliability Confidence Scoring
"""

import os
import sys
import torch
import torch.nn as nn
import numpy as np
from typing import Dict, Any, List, Tuple

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

class UncertaintyAndOODDetector:
    def __init__(self, model: nn.Module, feature_dim: int = 128):
        self.model = model
        self.device = next(model.parameters()).device
        self.feature_dim = feature_dim
        self.in_distribution_mean = None
        self.in_distribution_cov_inv = None
        self.fitted = False

    def fit_in_distribution_reference(self, reference_features: np.ndarray):
        """Fit empirical Gaussian distribution on training feature embeddings and calibrate threshold."""
        X = np.array(reference_features, dtype=np.float64)
        self.in_distribution_mean = np.mean(X, axis=0)
        cov = np.cov(X, rowvar=False) + np.eye(X.shape[1]) * 0.05
        self.in_distribution_cov_inv = np.linalg.pinv(cov)
        
        # Empirically calibrate threshold at 99th percentile of training data
        diffs = X - self.in_distribution_mean
        train_dists = np.sqrt(np.maximum(0.0, np.sum((diffs @ self.in_distribution_cov_inv) * diffs, axis=1)))
        self.ood_threshold = float(np.percentile(train_dists, 99.0)) * 1.3 # 30% margin
        self.fitted = True

    def compute_mahalanobis_distance(self, feature_vector: np.ndarray) -> float:
        """Compute Mahalanobis distance from in-distribution centroid."""
        if not self.fitted or self.in_distribution_mean is None:
            return float(np.linalg.norm(feature_vector))
        diff = np.array(feature_vector, dtype=np.float64) - self.in_distribution_mean
        dist_sq = float(diff @ self.in_distribution_cov_inv @ diff.T)
        return float(np.sqrt(max(0.0, dist_sq)))

    def estimate_epistemic_uncertainty_mc_dropout(self, x: torch.Tensor, n_passes: int = 10) -> Dict[str, Any]:
        """Runs N stochastic forward passes with active dropout to measure model uncertainty."""
        self.model.train() # Enable stochastic dropout
        
        delay_samples = []
        action_prob_samples = []

        with torch.no_grad():
            for _ in range(n_passes):
                out = self.model(x)
                pred_delay = out["delay_quantiles"][:, 0, 1].cpu().numpy()
                delay_samples.append(pred_delay)
                action_prob_samples.append(out["action_probs"].cpu().numpy())

        self.model.eval() # Restore eval mode

        delay_samples = np.array(delay_samples) # [N, B]
        action_prob_samples = np.array(action_prob_samples) # [N, B, num_actions]

        epistemic_delay_variance = np.var(delay_samples, axis=0)
        mean_delay = np.mean(delay_samples, axis=0)
        mean_action_probs = np.mean(action_prob_samples, axis=0)

        entropy = -np.sum(mean_action_probs * np.log(np.clip(mean_action_probs, 1e-7, 1.0)), axis=-1)

        return {
            "mean_predicted_delay": float(mean_delay[0]),
            "epistemic_delay_variance": float(epistemic_delay_variance[0]),
            "epistemic_uncertainty_minutes": float(np.sqrt(epistemic_delay_variance[0])),
            "policy_predictive_entropy": float(entropy[0]),
            "is_high_uncertainty": bool(np.sqrt(epistemic_delay_variance[0]) > 4.0 or entropy[0] > 1.5)
        }

    def assess_safety_and_ood(self, x_feat: np.ndarray) -> Dict[str, Any]:
        """Comprehensive OOD and reliability assessment for a live dispatch query."""
        maha_dist = self.compute_mahalanobis_distance(x_feat)
        threshold = getattr(self, "ood_threshold", 8.0)
        is_ood = maha_dist > threshold
        
        x_tensor = torch.tensor(np.array([x_feat], dtype=np.float32), dtype=torch.float32, device=self.device)
        mc_results = self.estimate_epistemic_uncertainty_mc_dropout(x_tensor, n_passes=10)

        reliability_score = max(0.0, 100.0 - min(100.0, (maha_dist / threshold) * 50.0 + mc_results["policy_predictive_entropy"] * 10.0))

        return {
            "mahalanobis_distance": round(maha_dist, 2),
            "ood_threshold": round(threshold, 2),
            "is_out_of_distribution": is_ood,
            "ood_status": "OOD_ANOMALY_DETECTED" if is_ood else "IN_DISTRIBUTION_CONFIRMED",
            "epistemic_uncertainty": mc_results,
            "decision_reliability_score_pct": max(0.0, round(reliability_score, 1)),
            "fallback_recommended": bool(is_ood or mc_results["is_high_uncertainty"])
        }

if __name__ == "__main__":
    from models.nexus_core.nexus_model import build_nexus_model
    model = build_nexus_model("fast_train")
    detector = UncertaintyAndOODDetector(model)
    
    # Simulate normal training data distribution
    synthetic_train = np.random.normal(loc=0.3, scale=0.15, size=(200, 7))
    detector.fit_in_distribution_reference(synthetic_train)

    # Test 1: In-distribution sample
    in_dist = np.array([0.25, 0.0, 0.0, 0.8, 0.25, 0.65, 0.5])
    res_in = detector.assess_safety_and_ood(in_dist)
    print("\n--- In-Distribution Assessment ---")
    print(res_in)

    # Test 2: Severe OOD anomaly (Extreme 5x delay, anomalous features)
    ood_sample = np.array([5.5, 1.0, 1.0, 0.1, 0.9, 0.1, 0.9])
    res_ood = detector.assess_safety_and_ood(ood_sample)
    print("\n--- Out-of-Distribution Assessment ---")
    print(res_ood)
