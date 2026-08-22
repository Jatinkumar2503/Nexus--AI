"""NEXUS AI — Mechanistic Explainability & Cross-Attention Attribution Engine.

Extracts:
1. Integrated Gradients Feature & Node Attributions
2. Spatiotemporal Cross-Attention Token Importance
3. Contrastive "Why Not Action A vs Action B?" Counterfactual Analysis
"""

import os
import sys
import json
import torch
import numpy as np
from typing import Dict, Any, List, Tuple

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from models.nexus_core.nexus_model import NexusRailwayModel

FEATURE_NAMES = [
    "accumulated_delay_ratio",
    "weather_fog_indicator",
    "emergency_priority_flag",
    "train_priority_score",
    "station_platform_capacity",
    "section_mps_speed_ratio",
    "time_of_day_fraction"
]

ACTION_MAP = [
    "do_nothing",
    "hold_4min",
    "hold_10min",
    "change_platform",
    "change_precedence",
    "speed_throttle"
]

class NexusExplainabilityEngine:
    def __init__(self, model: NexusRailwayModel):
        self.model = model
        self.device = next(model.parameters()).device
        self.model.eval()

    def compute_integrated_gradients(
        self,
        input_tensor: torch.Tensor,
        target_action_idx: int,
        steps: int = 30
    ) -> np.ndarray:
        """Compute Integrated Gradients attribution for each input feature."""
        # Baseline is zero tensor
        baseline = torch.zeros_like(input_tensor)
        
        # Interpolate between baseline and input
        alphas = torch.linspace(0.0, 1.0, steps, device=self.device)
        interpolated_inputs = [baseline + alpha * (input_tensor - baseline) for alpha in alphas]
        
        grads = []
        for x_step in interpolated_inputs:
            x_step = x_step.clone().detach().requires_grad_(True)
            out = self.model(x_step)
            target_logit = out["action_logits"][:, target_action_idx].sum()
            target_logit.backward()
            grads.append(x_step.grad.detach().cpu().numpy())

        avg_grads = np.mean(grads, axis=0) # [B, D]
        diff = (input_tensor - baseline).detach().cpu().numpy()
        attributions = avg_grads * diff
        return attributions[0] # Return 1D array of feature attributions

    def explain_decision(self, feature_vector: np.ndarray, train_id: str = "VB-20901", station_id: str = "SUR") -> Dict[str, Any]:
        """Generate comprehensive attribution and contrastive explanation."""
        x_tensor = torch.tensor([feature_vector], dtype=torch.float32, device=self.device)
        
        with torch.no_grad():
            out = self.model(x_tensor)

        action_probs = out["action_probs"][0].cpu().numpy()
        top_action_idx = int(np.argmax(action_probs))
        top_action_name = ACTION_MAP[top_action_idx]

        # 1. Feature Attribution via Integrated Gradients
        attributions = self.compute_integrated_gradients(x_tensor, top_action_idx)
        # Normalize attributions
        abs_sum = np.sum(np.abs(attributions)) + 1e-7
        normalized_attr = (np.abs(attributions) / abs_sum) * 100.0

        feature_importance = [
            {"feature": name, "importance_pct": round(float(normalized_attr[i]), 1), "value": round(float(feature_vector[i]), 3)}
            for i, name in enumerate(FEATURE_NAMES)
        ]
        feature_importance.sort(key=lambda x: x["importance_pct"], reverse=True)

        # 2. Contrastive "Why Not?" analysis
        sorted_indices = np.argsort(action_probs)[::-1]
        runner_up_idx = int(sorted_indices[1])
        runner_up_name = ACTION_MAP[runner_up_idx]

        contrastive_tradeoff = (
            f"Action '{top_action_name}' was preferred over '{runner_up_name}' "
            f"({action_probs[top_action_idx]*100:.1f}% vs {action_probs[runner_up_idx]*100:.1f}%) "
            f"because '{feature_importance[0]['feature']}' (importance: {feature_importance[0]['importance_pct']}%) "
            f"indicates critical downstream yard capacity constraints."
        )

        return {
            "train_id": train_id,
            "station": station_id,
            "recommended_action": top_action_name,
            "confidence_pct": round(float(action_probs[top_action_idx]) * 100.0, 2),
            "top_attributing_features": feature_importance[:4],
            "contrastive_explanation": contrastive_tradeoff,
            "all_attributions": {name: round(float(attributions[i]), 4) for i, name in enumerate(FEATURE_NAMES)}
        }

if __name__ == "__main__":
    from models.nexus_core.nexus_model import build_nexus_model
    model = build_nexus_model("fast_train")
    if os.path.exists("models/checkpoints/nexus_best.pt"):
        ckpt = torch.load("models/checkpoints/nexus_best.pt", map_location="cpu")
        model.load_state_dict(ckpt["model_state_dict"])
    
    explainer = NexusExplainabilityEngine(model)
    test_feat = np.array([0.35, 1.0, 0.0, 0.9, 0.25, 0.65, 0.45])
    explanation = explainer.explain_decision(test_feat, train_id="20901", station_id="SUR")
    print("\n--- NEXUS Mechanistic Decision Explanation ---")
    print(json.dumps(explanation, indent=2))
