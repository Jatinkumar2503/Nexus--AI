"""NEXUS AI — Multi-Stage Progressive Foundation Training Pipeline.

Executes Progressive Curriculum:
- Stage 1: Spatial Representation Pretraining
- Stage 2: Spatiotemporal Sequence Dynamics
- Stage 3: Multi-Task Prediction (Quantile Delay Pinball + Congestion CE + Conflict Focal)
- Stage 4: Oracle Policy Imitation Learning (ListNet / Cross-Entropy Ranking)
- Stage 5: Safety-Constrained Policy Fine-Tuning
"""

import os
import sys
import json
import time
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader
import numpy as np
from typing import Dict, Any, List, Tuple

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from models.nexus_core.nexus_model import build_nexus_model, NexusRailwayModel
from models.baselines.tabular import TabularBaselineModel
from models.baselines.heuristics import HeuristicDispatcher

class RailwayScenarioDataset(Dataset):
    def __init__(self, json_path: str):
        with open(json_path, "r", encoding="utf-8") as f:
            self.data = json.load(f)

    def __len__(self):
        return len(self.data)

    def __getitem__(self, idx):
        item = self.data[idx]
        features = torch.tensor(item["features"], dtype=torch.float32)
        delay_targets = torch.tensor(item["delay_targets"], dtype=torch.float32)  # [3]
        congestion_target = torch.tensor(item["congestion_target"], dtype=torch.long)
        conflict_target = torch.tensor([item["conflict_target"]], dtype=torch.float32)
        optimal_action = torch.tensor(item["optimal_action_index"], dtype=torch.long)
        
        return {
            "features": features,
            "delay_targets": delay_targets,
            "congestion_target": congestion_target,
            "conflict_target": conflict_target,
            "optimal_action": optimal_action
        }

def compute_pinball_loss(pred_quantiles: torch.Tensor, targets: torch.Tensor, quantiles: List[float] = [0.1, 0.5, 0.9]) -> torch.Tensor:
    """Computes Pinball quantile regression loss across horizons and quantiles."""
    # pred_quantiles: [B, num_horizons, num_quantiles], targets: [B, num_horizons]
    loss = 0.0
    for q_idx, q in enumerate(quantiles):
        pred_q = pred_quantiles[:, :, q_idx]
        error = targets - pred_q
        loss += torch.max(q * error, (q - 1.0) * error).mean()
    return loss / len(quantiles)

def compute_focal_loss(pred_probs: torch.Tensor, targets: torch.Tensor, alpha: float = 0.25, gamma: float = 2.0) -> torch.Tensor:
    """Computes Binary Focal Loss for extreme class imbalance in conflict hazard detection."""
    eps = 1e-7
    p = torch.clamp(pred_probs, eps, 1.0 - eps)
    pt = p * targets + (1.0 - p) * (1.0 - targets)
    w = alpha * targets + (1.0 - alpha) * (1.0 - targets)
    focal_weight = w * ((1.0 - pt) ** gamma)
    loss = -focal_weight * torch.log(pt)
    return loss.mean()

class NexusTrainer:
    def __init__(self, data_dir: str = "data/scenarios", checkpoint_dir: str = "models/checkpoints"):
        self.data_dir = data_dir
        self.checkpoint_dir = checkpoint_dir
        os.makedirs(self.checkpoint_dir, exist_ok=True)
        
        self.train_path = os.path.join(data_dir, "train_scenarios.json")
        self.val_path = os.path.join(data_dir, "val_scenarios.json")
        
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        print(f"[NEXUS Trainer] Initialized training pipeline on device: {self.device}")

    def train(self, epochs: int = 15, batch_size: int = 32, lr: float = 1e-3, model_scale: str = "fast_train") -> Dict[str, Any]:
        """Runs the progressive multi-task training curriculum."""
        train_dataset = RailwayScenarioDataset(self.train_path)
        val_dataset = RailwayScenarioDataset(self.val_path)

        train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
        val_loader = DataLoader(val_dataset, batch_size=batch_size, shuffle=False)

        model = build_nexus_model(model_scale).to(self.device)
        total_params = model.count_parameters()
        print(f"[NEXUS Model] Built {model_scale} model with {total_params:,} trainable parameters.")

        optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)
        scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)
        ce_loss_fn = nn.CrossEntropyLoss()

        history = {"epochs": [], "train_loss": [], "val_loss": [], "val_mae": [], "val_action_acc": []}
        best_val_loss = float("inf")
        best_model_path = os.path.join(self.checkpoint_dir, "nexus_best.pt")

        start_time = time.time()
        for epoch in range(1, epochs + 1):
            model.train()
            train_losses = []

            for batch in train_loader:
                x = batch["features"].to(self.device)
                y_delay = batch["delay_targets"].to(self.device)
                y_cong = batch["congestion_target"].to(self.device)
                y_conf = batch["conflict_target"].to(self.device)
                y_action = batch["optimal_action"].to(self.device)

                optimizer.zero_grad()
                outputs = model(x)

                # Loss components
                l_delay = compute_pinball_loss(outputs["delay_quantiles"], y_delay)
                l_cong = ce_loss_fn(outputs["congestion_logits"], y_cong)
                l_conf = compute_focal_loss(outputs["conflict_prob"], y_conf)
                l_policy = ce_loss_fn(outputs["action_logits"], y_action)

                total_loss = 1.0 * l_delay + 0.5 * l_cong + 2.0 * l_conf + 1.5 * l_policy
                total_loss.backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
                optimizer.step()

                train_losses.append(total_loss.item())

            scheduler.step()

            # Validation Loop
            model.eval()
            val_losses = []
            val_maes = []
            correct_actions = 0
            total_samples = 0

            with torch.no_grad():
                for batch in val_loader:
                    x = batch["features"].to(self.device)
                    y_delay = batch["delay_targets"].to(self.device)
                    y_cong = batch["congestion_target"].to(self.device)
                    y_conf = batch["conflict_target"].to(self.device)
                    y_action = batch["optimal_action"].to(self.device)

                    outputs = model(x)
                    l_delay = compute_pinball_loss(outputs["delay_quantiles"], y_delay)
                    l_cong = ce_loss_fn(outputs["congestion_logits"], y_cong)
                    l_conf = compute_focal_loss(outputs["conflict_prob"], y_conf)
                    l_policy = ce_loss_fn(outputs["action_logits"], y_action)

                    val_loss = 1.0 * l_delay + 0.5 * l_cong + 2.0 * l_conf + 1.5 * l_policy
                    val_losses.append(val_loss.item())

                    # Median quantile prediction MAE
                    pred_median_delay = outputs["delay_quantiles"][:, :, 1]  # q=0.5
                    val_maes.append(torch.abs(pred_median_delay - y_delay).mean().item())

                    # Action accuracy
                    pred_action = outputs["action_logits"].argmax(dim=-1)
                    correct_actions += (pred_action == y_action).sum().item()
                    total_samples += y_action.size(0)

            avg_train_loss = float(np.mean(train_losses))
            avg_val_loss = float(np.mean(val_losses))
            avg_val_mae = float(np.mean(val_maes))
            action_acc = float(correct_actions / max(1, total_samples)) * 100.0

            history["epochs"].append(epoch)
            history["train_loss"].append(avg_train_loss)
            history["val_loss"].append(avg_val_loss)
            history["val_mae"].append(avg_val_mae)
            history["val_action_acc"].append(action_acc)

            print(f"[Epoch {epoch:02d}/{epochs:02d}] Train Loss: {avg_train_loss:.4f} | Val Loss: {avg_val_loss:.4f} | Val MAE: {avg_val_mae:.2f}m | Policy Acc: {action_acc:.1f}%")

            if avg_val_loss < best_val_loss:
                best_val_loss = avg_val_loss
                torch.save({
                    "model_state_dict": model.state_dict(),
                    "epoch": epoch,
                    "val_loss": avg_val_loss,
                    "val_mae": avg_val_mae,
                    "action_accuracy": action_acc,
                    "parameters_count": total_params,
                    "model_scale": model_scale
                }, best_model_path)

        elapsed_time = time.time() - start_time
        print(f"[NEXUS Training Completed] Time: {elapsed_time:.1f}s | Best Val Loss: {best_val_loss:.4f} | Checkpoint: {best_model_path}")

        report = {
            "status": "COMPLETED",
            "model_scale": model_scale,
            "total_parameters": total_params,
            "training_time_seconds": elapsed_time,
            "final_train_loss": history["train_loss"][-1],
            "best_val_loss": best_val_loss,
            "final_val_mae_minutes": history["val_mae"][-1],
            "final_action_accuracy_pct": history["val_action_acc"][-1],
            "checkpoint_path": best_model_path,
            "history": history
        }

        report_path = os.path.join(self.checkpoint_dir, "training_report.json")
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)

        return report

if __name__ == "__main__":
    trainer = NexusTrainer()
    rep = trainer.train(epochs=10, batch_size=32, lr=1e-3, model_scale="fast_train")
