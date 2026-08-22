"""NEXUS AI — Knowledge Distillation Engine.

Distills deep spatiotemporal representations from the 318M Heavy Teacher Model
into the lightweight 1.45M Edge Student Model using Temperature-Scaled KL Divergence Loss.

Loss Equation:
L_KD = alpha * L_Task + (1 - alpha) * T^2 * KL_Divergence(P_Student(logits/T), P_Teacher(logits/T))
"""

import os
import sys
import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Dict, Any

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from models.nexus_core.nexus_model import build_nexus_model, NexusRailwayModel

class KnowledgeDistillationLoss(nn.Module):
    def __init__(self, temperature: float = 3.0, alpha: float = 0.4):
        super().__init__()
        self.temperature = temperature
        self.alpha = alpha
        self.kl_div = nn.KLDivLoss(reduction="batchmean")
        self.ce_loss = nn.CrossEntropyLoss()
        self.mse_loss = nn.MSELoss()

    def forward(
        self,
        student_outputs: Dict[str, torch.Tensor],
        teacher_outputs: Dict[str, torch.Tensor],
        targets: torch.Tensor
    ) -> torch.Tensor:
        # Task Loss (Hard Targets)
        task_loss = self.ce_loss(student_outputs["action_logits"], targets)

        # Distillation Loss (Soft Targets KL Divergence)
        student_logits_scaled = F.log_softmax(student_outputs["action_logits"] / self.temperature, dim=-1)
        teacher_logits_scaled = F.softmax(teacher_outputs["action_logits"] / self.temperature, dim=-1)

        kd_loss = self.kl_div(student_logits_scaled, teacher_logits_scaled) * (self.temperature ** 2)

        # Total Distillation Loss
        total_loss = self.alpha * task_loss + (1.0 - self.alpha) * kd_loss
        return total_loss

def run_distillation_step(
    teacher_model: NexusRailwayModel,
    student_model: NexusRailwayModel,
    sample_batch: torch.Tensor,
    target_actions: torch.Tensor,
    optimizer: torch.optim.Optimizer
) -> float:
    teacher_model.eval()
    student_model.train()

    with torch.no_grad():
        teacher_outputs = teacher_model(sample_batch)

    student_outputs = student_model(sample_batch)

    loss_fn = KnowledgeDistillationLoss(temperature=3.0, alpha=0.4)
    loss = loss_fn(student_outputs, teacher_outputs, target_actions)

    optimizer.zero_grad()
    loss.backward()
    optimizer.step()

    return loss.item()

if __name__ == "__main__":
    print("[Distillation Pipeline] Initializing Teacher (265m) and Student (fast_train)...")
    teacher = build_nexus_model("265m")
    student = build_nexus_model("fast_train")

    dummy_input = torch.randn(8, 7)
    dummy_targets = torch.randint(0, 6, (8,))

    opt = torch.optim.AdamW(student.parameters(), lr=1e-3)
    loss_val = run_distillation_step(teacher, student, dummy_input, dummy_targets, opt)

    print(f"[Distillation Pipeline] Single step distillation completed cleanly. Loss: {loss_val:.4f}")
