"""NEXUS AI — Multimodal Cross-Attention Fusion Transformer."""

import torch
import torch.nn as nn
import torch.nn.functional as F

class CrossAttentionFusionBlock(nn.Module):
    def __init__(self, d_model: int = 128, num_heads: int = 4):
        super().__init__()
        self.attn = nn.MultiheadAttention(embed_dim=d_model, num_heads=num_heads, batch_first=True)
        self.ffn = nn.Sequential(
            nn.Linear(d_model, d_model * 4),
            nn.GELU(),
            nn.Linear(d_model * 4, d_model)
        )
        self.norm1 = nn.LayerNorm(d_model)
        self.norm2 = nn.LayerNorm(d_model)

    def forward(self, query: torch.Tensor, context: torch.Tensor) -> torch.Tensor:
        nq = self.norm1(query)
        attn_out, _ = self.attn(nq, context, context)
        query = query + attn_out
        return query + self.ffn(self.norm2(query))

class SpatiotemporalFusionTransformer(nn.Module):
    def __init__(self, d_model: int = 128, num_layers: int = 4):
        super().__init__()
        self.blocks = nn.ModuleList([
            CrossAttentionFusionBlock(d_model=d_model, num_heads=4)
            for _ in range(num_layers)
        ])
        self.norm = nn.LayerNorm(d_model)

    def forward(self, graph_emb: torch.Tensor, temporal_emb: torch.Tensor) -> torch.Tensor:
        h = graph_emb
        for block in self.blocks:
            h = block(query=h, context=temporal_emb)
        return self.norm(h)
