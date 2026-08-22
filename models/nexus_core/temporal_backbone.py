"""NEXUS AI — Causal Temporal Dynamics Sequence Backbone."""

import torch
import torch.nn as nn
import torch.nn.functional as F

class CausalTemporalBlock(nn.Module):
    def __init__(self, hidden_dim: int, num_heads: int = 4):
        super().__init__()
        self.num_heads = num_heads
        self.head_dim = hidden_dim // num_heads

        self.q_proj = nn.Linear(hidden_dim, hidden_dim, bias=False)
        self.k_proj = nn.Linear(hidden_dim, hidden_dim, bias=False)
        self.v_proj = nn.Linear(hidden_dim, hidden_dim, bias=False)
        self.out_proj = nn.Linear(hidden_dim, hidden_dim)

        self.ffn = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim * 4),
            nn.GELU(),
            nn.Linear(hidden_dim * 4, hidden_dim)
        )
        self.norm1 = nn.LayerNorm(hidden_dim)
        self.norm2 = nn.LayerNorm(hidden_dim)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        B, T, D = x.shape
        nx = self.norm1(x)
        Q = self.q_proj(nx).view(B, T, self.num_heads, self.head_dim).transpose(1, 2)
        K = self.k_proj(nx).view(B, T, self.num_heads, self.head_dim).transpose(1, 2)
        V = self.v_proj(nx).view(B, T, self.num_heads, self.head_dim).transpose(1, 2)

        scores = torch.matmul(Q, K.transpose(-2, -1)) / (self.head_dim ** 0.5)
        
        # Enforce strict causality: upper triangular mask
        causal_mask = torch.triu(torch.ones(T, T, device=x.device), diagonal=1).bool()
        scores = scores.masked_fill(causal_mask.unsqueeze(0).unsqueeze(0), float('-inf'))

        attn = F.softmax(scores, dim=-1)
        out = torch.matmul(attn, V).transpose(1, 2).contiguous().view(B, T, D)
        
        x = x + self.out_proj(out)
        return x + self.ffn(self.norm2(x))

class CausalTemporalBackbone(nn.Module):
    def __init__(self, in_dim: int = 128, hidden_dim: int = 128, num_layers: int = 4):
        super().__init__()
        self.input_proj = nn.Linear(in_dim, hidden_dim)
        self.blocks = nn.ModuleList([
            CausalTemporalBlock(hidden_dim, num_heads=4)
            for _ in range(num_layers)
        ])
        self.norm = nn.LayerNorm(hidden_dim)

    def forward(self, seq_features: torch.Tensor) -> torch.Tensor:
        h = self.input_proj(seq_features)
        for block in self.blocks:
            h = block(h)
        return self.norm(h)
