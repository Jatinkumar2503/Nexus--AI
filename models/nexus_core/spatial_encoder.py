"""NEXUS AI — Heterogeneous Graph Attention Spatial Encoder."""

import torch
import torch.nn as nn
import torch.nn.functional as F

class RelationalGraphAttentionLayer(nn.Module):
    def __init__(self, in_dim: int, out_dim: int, num_heads: int = 4):
        super().__init__()
        self.in_dim = in_dim
        self.out_dim = out_dim
        self.num_heads = num_heads
        self.head_dim = out_dim // num_heads

        self.q_proj = nn.Linear(in_dim, out_dim, bias=False)
        self.k_proj = nn.Linear(in_dim, out_dim, bias=False)
        self.v_proj = nn.Linear(in_dim, out_dim, bias=False)
        self.out_proj = nn.Linear(out_dim, out_dim)
        self.norm = nn.LayerNorm(out_dim)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        B, N, D = x.shape
        nx = self.norm(x)
        Q = self.q_proj(nx).view(B, N, self.num_heads, self.head_dim).transpose(1, 2)
        K = self.k_proj(nx).view(B, N, self.num_heads, self.head_dim).transpose(1, 2)
        V = self.v_proj(nx).view(B, N, self.num_heads, self.head_dim).transpose(1, 2)

        scores = torch.matmul(Q, K.transpose(-2, -1)) / (self.head_dim ** 0.5)
        attn = F.softmax(scores, dim=-1)
        out = torch.matmul(attn, V).transpose(1, 2).contiguous().view(B, N, self.out_dim)
        
        return x + self.out_proj(out)

class HeteroSpatialEncoder(nn.Module):
    def __init__(self, node_in_dim: int = 16, hidden_dim: int = 128, num_layers: int = 4):
        super().__init__()
        self.input_proj = nn.Linear(node_in_dim, hidden_dim)
        self.layers = nn.ModuleList([
            RelationalGraphAttentionLayer(hidden_dim, hidden_dim, num_heads=4)
            for _ in range(num_layers)
        ])
        self.norm = nn.LayerNorm(hidden_dim)

    def forward(self, node_features: torch.Tensor) -> torch.Tensor:
        h = self.input_proj(node_features)
        for layer in self.layers:
            h = layer(h)
        return self.norm(h)
