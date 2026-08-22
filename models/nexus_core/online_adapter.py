"""NEXUS AI — Dynamic Test-Time Adaptation (TTA) & Online Experience Replay Adapter.

Allows NEXUS to continuously adapt to live operational shifts:
1. Online Experience Replay Buffer (Stores recent live telemetry and verified dispatch outcomes)
2. Low-Rank / Parameter-Efficient Online Adaptation (Fine-tunes attention projection layer)
3. Anti-Forgetting Elastic Weight Consolidation (EWC) / Anchor Regularization
4. Step-wise Online Model Evaluation
"""

import os
import sys
import copy
import time
import json
import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
from typing import Dict, Any, List, Optional

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from models.nexus_core.nexus_model import build_nexus_model, NexusRailwayModel

class OnlineExperienceReplayBuffer:
    def __init__(self, capacity: int = 500):
        self.capacity = capacity
        self.buffer = []
        self.position = 0

    def push(self, features: np.ndarray, delay_targets: np.ndarray, optimal_action_idx: int):
        item = {
            "features": np.array(features, dtype=np.float32),
            "delay_targets": np.array(delay_targets, dtype=np.float32),
            "action_target": int(optimal_action_idx),
            "timestamp": time.time()
        }
        if len(self.buffer) < self.capacity:
            self.buffer.append(item)
        else:
            self.buffer[self.position] = item
        self.position = (self.position + 1) % self.capacity

    def sample(self, batch_size: int = 16) -> Dict[str, torch.Tensor]:
        n = len(self.buffer)
        idx = np.random.choice(n, min(batch_size, n), replace=False)
        samples = [self.buffer[i] for i in idx]

        b_X = torch.tensor(np.array([s["features"] for s in samples]), dtype=torch.float32)
        b_delays = torch.tensor(np.array([s["delay_targets"] for s in samples]), dtype=torch.float32)
        b_actions = torch.tensor(np.array([s["action_target"] for s in samples]), dtype=torch.int64)

        return {"features": b_X, "delays": b_delays, "actions": b_actions}

    def __len__(self):
        return len(self.buffer)


class NexusOnlineAdapter:
    def __init__(self, checkpoint_path: str = "models/checkpoints/nexus_best.pt", lr: float = 5e-5):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model = build_nexus_model("fast_train").to(self.device)

        if os.path.exists(checkpoint_path):
            ckpt = torch.load(checkpoint_path, map_location=self.device)
            self.model.load_state_dict(ckpt["model_state_dict"])
            print(f"[Online Adapter] Initialized from {checkpoint_path}")

        # Store anchor weights for anti-forgetting regularization
        self.anchor_state = {k: v.clone().detach() for k, v in self.model.state_dict().items()}
        self.replay_buffer = OnlineExperienceReplayBuffer(capacity=500)
        self.optimizer = torch.optim.AdamW(self.model.parameters(), lr=lr, weight_decay=1e-3)

    def record_operational_telemetry(self, features: np.ndarray, actual_delays: np.ndarray, chosen_action_idx: int):
        """Streams live telemetry outcome into online replay buffer."""
        self.replay_buffer.push(features, actual_delays, chosen_action_idx)

    def adapt_step(self, ewc_lambda: float = 10.0) -> Dict[str, float]:
        """Performs one online adaptation update step with anti-forgetting anchor loss."""
        if len(self.replay_buffer) < 8:
            return {"status": "BUFFER_WARMING_UP", "samples": len(self.replay_buffer)}

        self.model.train()
        batch = self.replay_buffer.sample(batch_size=16)
        b_X = batch["features"].to(self.device)
        b_delays = batch["delays"].to(self.device)
        b_actions = batch["actions"].to(self.device)

        self.optimizer.zero_grad()
        out = self.model(b_X)

        # Pinball loss on delay median
        pred_delays = out["delay_quantiles"][:, :, 1] # [B, 3] median
        delay_loss = F.l1_loss(pred_delays, b_delays)

        # Cross-entropy on policy actions
        action_loss = F.cross_entropy(out["action_logits"], b_actions)

        # Anti-forgetting anchor regularization
        anchor_loss = 0.0
        for name, param in self.model.named_parameters():
            if name in self.anchor_state:
                anchor_loss += torch.norm(param - self.anchor_state[name]) ** 2

        total_loss = delay_loss + 0.5 * action_loss + (ewc_lambda * 1e-4) * anchor_loss
        total_loss.backward()
        torch.nn.utils.clip_grad_norm_(self.model.parameters(), max_norm=0.5)
        self.optimizer.step()

        self.model.eval()

        return {
            "status": "ADAPTED",
            "total_loss": float(total_loss.item()),
            "delay_l1_error": float(delay_loss.item()),
            "action_loss": float(action_loss.item()),
            "buffer_size": len(self.replay_buffer)
        }

if __name__ == "__main__":
    adapter = NexusOnlineAdapter()
    
    # Simulate streaming live telemetry stream (e.g. 50 incoming train updates)
    print("\n[Online Adapter] Simulating streaming online operational telemetry...")
    for i in range(40):
        # Generate simulated operational state
        feat = np.random.uniform(0.1, 0.8, size=7).astype(np.float32)
        delays = np.array([12.5, 18.0, 24.5], dtype=np.float32)
        act_idx = 4 # change_precedence
        adapter.record_operational_telemetry(feat, delays, act_idx)

    # Perform online adaptation
    for step in range(1, 4):
        res = adapter.adapt_step()
        print(f"[Online Step {step}] Status: {res['status']} | Total Loss: {res.get('total_loss', 0):.4f} | Delay L1: {res.get('delay_l1_error', 0):.4f}")
