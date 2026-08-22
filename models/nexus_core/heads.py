"""NEXUS AI — Multi-Task Prediction & Action Policy Ranking Heads."""

import torch
import torch.nn as nn
import torch.nn.functional as F

class MultiTaskPredictionHeads(nn.Module):
    def __init__(self, d_model: int = 128, num_quantiles: int = 3, num_horizons: int = 3, num_actions: int = 6):
        super().__init__()
        self.d_model = d_model
        self.num_quantiles = num_quantiles
        self.num_horizons = num_horizons

        # 1. Multi-Horizon Quantile Delay Head (Outputs: horizons x quantiles [q=0.1, 0.5, 0.9])
        self.delay_head = nn.Sequential(
            nn.Linear(d_model, d_model),
            nn.GELU(),
            nn.Linear(d_model, num_horizons * num_quantiles)
        )

        # 2. Section Congestion Classifier Head (4 classes: LOW, MEDIUM, HIGH, CRITICAL)
        self.congestion_head = nn.Sequential(
            nn.Linear(d_model, d_model // 2),
            nn.GELU(),
            nn.Linear(d_model // 2, 4)
        )

        # 3. Rare Conflict Hazard Head (Binary Focal Sigmoid)
        self.conflict_head = nn.Sequential(
            nn.Linear(d_model, d_model // 2),
            nn.GELU(),
            nn.Linear(d_model // 2, 1)
        )

        # 4. Action Policy Ranking Head (Scores candidate dispatch actions)
        self.policy_head = nn.Sequential(
            nn.Linear(d_model, d_model),
            nn.GELU(),
            nn.Linear(d_model, num_actions)
        )

    def forward(self, fused_features: torch.Tensor) -> dict:
        # Global pooling if sequence/node dimension present
        if fused_features.dim() == 3:
            pooled = fused_features.mean(dim=1)
        else:
            pooled = fused_features

        raw_quantiles = self.delay_head(pooled).view(-1, self.num_horizons, self.num_quantiles)
        # Non-crossing monotonic parameterization: q0.1 = base - softplus(d1), q0.5 = base, q0.9 = base + softplus(d2)
        base = raw_quantiles[:, :, 1:2]
        d1 = F.softplus(raw_quantiles[:, :, 0:1])
        d2 = F.softplus(raw_quantiles[:, :, 2:3])
        q0_1 = base - d1
        q0_5 = base
        q0_9 = base + d2
        delay_quantiles = torch.cat([q0_1, q0_5, q0_9], dim=-1)

        congestion_logits = self.congestion_head(pooled)
        conflict_logits = self.conflict_head(pooled)
        action_logits = self.policy_head(pooled)

        return {
            "delay_quantiles": delay_quantiles,
            "congestion_logits": congestion_logits,
            "conflict_logits": conflict_logits,
            "conflict_prob": torch.sigmoid(conflict_logits),
            "action_logits": action_logits,
            "action_probs": F.softmax(action_logits, dim=-1)
        }
