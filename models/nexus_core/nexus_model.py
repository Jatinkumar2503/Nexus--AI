"""NEXUS AI — Unified Foundation Spatiotemporal Railway Architecture.

Combines:
- Spatial Hetero-GAT Encoder
- Causal Temporal Dynamics Backbone
- Spatiotemporal Cross-Attention Fusion Transformer
- Multi-Task Predictive & Policy Ranking Heads
- Factory method for Parameter Scaling Study (10M -> 265M)
"""

import os
import sys
import torch
import torch.nn as nn
from typing import Dict, Any

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from models.nexus_core.spatial_encoder import HeteroSpatialEncoder
from models.nexus_core.temporal_backbone import CausalTemporalBackbone
from models.nexus_core.fusion_transformer import SpatiotemporalFusionTransformer
from models.nexus_core.heads import MultiTaskPredictionHeads

class NexusRailwayModel(nn.Module):
    def __init__(self, node_in_dim: int = 7, d_model: int = 128, num_layers: int = 4, num_actions: int = 6):
        super().__init__()
        self.d_model = d_model
        self.spatial_encoder = HeteroSpatialEncoder(node_in_dim=node_in_dim, hidden_dim=d_model, num_layers=num_layers)
        self.temporal_backbone = CausalTemporalBackbone(in_dim=d_model, hidden_dim=d_model, num_layers=num_layers)
        self.fusion_transformer = SpatiotemporalFusionTransformer(d_model=d_model, num_layers=num_layers)
        self.heads = MultiTaskPredictionHeads(d_model=d_model, num_quantiles=3, num_horizons=3, num_actions=num_actions)

    def forward(self, x: torch.Tensor) -> Dict[str, torch.Tensor]:
        # Handle input batching shape [B, D] -> [B, 1, D]
        if x.dim() == 2:
            x_seq = x.unsqueeze(1)
        else:
            x_seq = x

        spatial_emb = self.spatial_encoder(x_seq)
        temporal_emb = self.temporal_backbone(spatial_emb)
        fused_emb = self.fusion_transformer(spatial_emb, temporal_emb)
        outputs = self.heads(fused_emb)
        return outputs

    def count_parameters(self) -> int:
        """Returns total trainable parameter count."""
        return sum(p.numel() for p in self.parameters() if p.requires_grad)

def build_nexus_model(model_scale: str = "medium") -> NexusRailwayModel:
    """Model factory supporting scaling study from 10M to 265M target architectures."""
    scale_configs = {
        "10m": {"d_model": 256, "num_layers": 4},
        "50m": {"d_model": 512, "num_layers": 8},
        "100m": {"d_model": 768, "num_layers": 12},
        "265m": {"d_model": 1280, "num_layers": 16},
        "fast_train": {"d_model": 128, "num_layers": 3}
    }
    cfg = scale_configs.get(model_scale, scale_configs["fast_train"])
    return NexusRailwayModel(node_in_dim=7, d_model=cfg["d_model"], num_layers=cfg["num_layers"], num_actions=6)
