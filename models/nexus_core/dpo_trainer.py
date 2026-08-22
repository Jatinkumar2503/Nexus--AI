"""NEXUS AI — Direct Preference Optimization (DPO) & Multi-Objective Policy Alignment.

Aligns the NEXUS action policy head directly with multi-objective human / CP-SAT preference pairs:
y_w (preferred action with lower multi-objective cost) vs. y_l (dispreferred action with higher cost / delay).

Implements the closed-form DPO objective:
L_DPO(theta; pi_ref) = -E_{(x, y_w, y_l)} [ log sigma( beta * log(pi_theta(y_w|x) / pi_ref(y_w|x)) - beta * log(pi_theta(y_l|x) / pi_ref(y_l|x)) ) ]
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
from typing import Dict, Any, List, Tuple

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from models.nexus_core.nexus_model import build_nexus_model, NexusRailwayModel

class NexusDPOTrainer:
    def __init__(self, beta: float = 0.1, lr: float = 1e-4, model_scale: str = "fast_train"):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.beta = beta
        
        # Policy model to train
        self.policy_model = build_nexus_model(model_scale).to(self.device)
        
        # Frozen reference model pi_ref
        self.ref_model = copy.deepcopy(self.policy_model)
        for param in self.ref_model.parameters():
            param.requires_grad = False
        self.ref_model.eval()

        self.optimizer = torch.optim.AdamW(self.policy_model.parameters(), lr=lr, weight_decay=1e-4)

    def load_pretrained_weights(self, checkpoint_path: str = "models/checkpoints/nexus_best.pt"):
        """Load initial foundation model weights into policy and reference models."""
        if os.path.exists(checkpoint_path):
            ckpt = torch.load(checkpoint_path, map_location=self.device)
            self.policy_model.load_state_dict(ckpt["model_state_dict"])
            self.ref_model.load_state_dict(ckpt["model_state_dict"])
            print(f"[DPO Trainer] Successfully initialized policy and reference models from {checkpoint_path}")

    def compute_dpo_loss(
        self,
        features: torch.Tensor,
        action_w: torch.Tensor,
        action_l: torch.Tensor
    ) -> Tuple[torch.Tensor, Dict[str, float]]:
        """Compute DPO loss over winning (y_w) and losing (y_l) action pairs."""
        # 1. Policy model log-probs
        policy_out = self.policy_model(features)
        policy_logits = policy_out["action_logits"] # [B, num_actions]
        policy_log_probs = F.log_softmax(policy_logits, dim=-1)

        pi_log_w = policy_log_probs.gather(dim=-1, index=action_w.unsqueeze(-1)).squeeze(-1)
        pi_log_l = policy_log_probs.gather(dim=-1, index=action_l.unsqueeze(-1)).squeeze(-1)

        # 2. Reference model log-probs (frozen)
        with torch.no_grad():
            ref_out = self.ref_model(features)
            ref_logits = ref_out["action_logits"]
            ref_log_probs = F.log_softmax(ref_logits, dim=-1)

            ref_log_w = ref_log_probs.gather(dim=-1, index=action_w.unsqueeze(-1)).squeeze(-1)
            ref_log_l = ref_log_probs.gather(dim=-1, index=action_l.unsqueeze(-1)).squeeze(-1)

        # 3. Log ratio calculation
        log_ratio_w = pi_log_w - ref_log_w
        log_ratio_l = pi_log_l - ref_log_l

        # 4. Implicit reward margins
        implicit_margin = self.beta * (log_ratio_w - log_ratio_l)
        loss = -F.logsigmoid(implicit_margin).mean()

        # Metrics
        reward_accuracies = (implicit_margin > 0.0).float().mean().item()
        margin_mean = implicit_margin.mean().item()

        metrics = {
            "dpo_loss": float(loss.item()),
            "preference_accuracy": float(reward_accuracies) * 100.0,
            "implicit_margin": float(margin_mean)
        }
        return loss, metrics

    def train_dpo_epoch(self, dataset: List[Dict[str, Any]], batch_size: int = 32) -> Dict[str, float]:
        """Train one epoch of Direct Preference Optimization on scenario preference pairs."""
        self.policy_model.train()
        
        # Build preference pairs (y_w = optimal action from CP-SAT, y_l = sub-optimal heuristic action)
        X_list, w_list, l_list = [], [], []
        for item in dataset:
            opt_idx = item["optimal_action_index"]
            cands = item.get("candidate_actions", [])
            
            # Find a lower-ranked or invalid action as the dispreferred negative
            negative_idx = (opt_idx + 1) % 6
            for c in cands:
                if not c.get("is_safety_valid", True):
                    act_dict = c.get("action", {})
                    act_type = act_dict.get("action_type", "do_nothing") if isinstance(act_dict, dict) else str(act_dict)
                    break

            X_list.append(item["features"])
            w_list.append(opt_idx)
            l_list.append(negative_idx)

        X_tensor = torch.tensor(np.array(X_list, dtype=np.float32), device=self.device)
        w_tensor = torch.tensor(np.array(w_list, dtype=np.int64), device=self.device)
        l_tensor = torch.tensor(np.array(l_list, dtype=np.int64), device=self.device)

        n_samples = len(X_list)
        epoch_losses, epoch_accs, epoch_margins = [], [], []

        indices = np.arange(n_samples)
        np.random.shuffle(indices)

        for start in range(0, n_samples, batch_size):
            end = min(start + batch_size, n_samples)
            b_idx = indices[start:end]

            b_X = X_tensor[b_idx]
            b_w = w_tensor[b_idx]
            b_l = l_tensor[b_idx]

            self.optimizer.zero_grad()
            loss, metrics = self.compute_dpo_loss(b_X, b_w, b_l)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(self.policy_model.parameters(), max_norm=1.0)
            self.optimizer.step()

            epoch_losses.append(metrics["dpo_loss"])
            epoch_accs.append(metrics["preference_accuracy"])
            epoch_margins.append(metrics["implicit_margin"])

        return {
            "avg_dpo_loss": float(np.mean(epoch_losses)),
            "avg_preference_accuracy_pct": float(np.mean(epoch_accs)),
            "avg_implicit_margin": float(np.mean(epoch_margins))
        }

if __name__ == "__main__":
    trainer = NexusDPOTrainer(beta=0.1, lr=1e-4)
    trainer.load_pretrained_weights("models/checkpoints/nexus_best.pt")

    # Load training dataset
    with open("data/scenarios/train_scenarios.json", "r", encoding="utf-8") as f:
        train_data = json.load(f)

    print(f"\n[DPO Trainer] Starting Direct Preference Optimization on {len(train_data)} preference pairs...")
    for ep in range(1, 4):
        t0 = time.perf_counter()
        stats = trainer.train_dpo_epoch(train_data, batch_size=32)
        t1 = time.perf_counter()
        print(f"[DPO Epoch {ep:02d}/03] Loss: {stats['avg_dpo_loss']:.4f} | Preference Acc: {stats['avg_preference_accuracy_pct']:.1f}% | Margin: {stats['avg_implicit_margin']:.3f} | Time: {t1-t0:.2f}s")
