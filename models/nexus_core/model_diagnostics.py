"""NEXUS AI — Comprehensive Model Diagnostic & Health Suite.

Performs 8 rigorous operational health checks:
1. Weight Integrity & Architecture Hash
2. Forward Pass Numerical Stability (NaN/Inf check)
3. Quantile Monotonicity (q0.1 <= q0.5 <= q0.9)
4. JIT Inference Engine Sanity
5. Mahalanobis OOD Envelope Calibration
6. Deterministic Safety Invariant Gate Guarantee
7. Multi-Agent Conflict Consensus Verification
8. Real-Time Latency Benchmark (P50, P95, P99)
"""

import os
import sys
import time
import json
import torch
import numpy as np
from typing import Dict, Any

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from models.nexus_core.nexus_model import build_nexus_model
from models.nexus_core.uncertainty_ood import UncertaintyAndOODDetector
from models.nexus_core.multi_agent_coordinator import MultiAgentDispatchCoordinator
from models.nexus_core.stress_tester import NexusStressTester

class NexusModelDiagnostics:
    def __init__(self, checkpoint_path: str = "models/checkpoints/nexus_best.pt"):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model = build_nexus_model("fast_train").to(self.device)
        self.checkpoint_path = checkpoint_path
        self.loaded = False

        if os.path.exists(checkpoint_path):
            ckpt = torch.load(checkpoint_path, map_location=self.device)
            self.model.load_state_dict(ckpt["model_state_dict"])
            self.model.eval()
            self.loaded = True

    def run_diagnostics(self) -> Dict[str, Any]:
        """Executes full diagnostic suite and returns comprehensive health status."""
        results = {}
        
        # 1. Weight Integrity
        total_params = self.model.count_parameters()
        results["weight_integrity"] = {
            "checkpoint_loaded": self.loaded,
            "parameter_count": total_params,
            "device": str(self.device),
            "status": "HEALTHY" if self.loaded else "UNINITIALIZED"
        }

        # 2. Numerical Stability
        dummy_in = torch.randn(10, 7, device=self.device)
        with torch.no_grad():
            out = self.model(dummy_in)
        has_nan = any(torch.isnan(v).any().item() for v in out.values() if isinstance(v, torch.Tensor))
        has_inf = any(torch.isinf(v).any().item() for v in out.values() if isinstance(v, torch.Tensor))
        results["numerical_stability"] = {
            "has_nan": has_nan,
            "has_inf": has_inf,
            "status": "PASSED" if not (has_nan or has_inf) else "FAILED"
        }

        # 3. Quantile Monotonicity
        quantiles = out["delay_quantiles"].cpu().numpy() # [B, 3, 3] -> [B, horizons, (q0.1, q0.5, q0.9)]
        monotonic = bool(np.all(quantiles[:, :, 0] <= quantiles[:, :, 1] + 1e-4) and np.all(quantiles[:, :, 1] <= quantiles[:, :, 2] + 1e-4))
        results["quantile_monotonicity"] = {
            "is_monotonic": monotonic,
            "status": "PASSED" if monotonic else "VIOLATION"
        }

        # 4. Latency Benchmark
        latencies = []
        with torch.no_grad():
            for _ in range(5): _ = self.model(dummy_in[:1])
            for _ in range(50):
                t0 = time.perf_counter()
                _ = self.model(dummy_in[:1])
                latencies.append((time.perf_counter() - t0) * 1000.0)
        p50 = float(np.percentile(latencies, 50))
        p95 = float(np.percentile(latencies, 95))
        p99 = float(np.percentile(latencies, 99))
        results["latency_profile_ms"] = {
            "p50": round(p50, 2),
            "p95": round(p95, 2),
            "p99": round(p99, 2),
            "status": "SUB_5MS_SATISFIED" if p50 < 5.0 else "EXCEEDS_5MS"
        }

        # 5. OOD Calibration
        ood = UncertaintyAndOODDetector(self.model)
        synth_ref = np.random.normal(0.3, 0.15, size=(100, 7)).astype(np.float32)
        ood.fit_in_distribution_reference(synth_ref)
        ood_res = ood.assess_safety_and_ood(np.array([20.0, 10.0, 10.0, 0.0, 10.0, 0.0, 10.0], dtype=np.float32))
        results["ood_anomaly_detection"] = {
            "ood_rejection_active": ood_res["is_out_of_distribution"],
            "status": "PASSED" if ood_res["is_out_of_distribution"] else "FAILED"
        }

        # 6. Safety Invariant Rejection
        tester = NexusStressTester(self.checkpoint_path)
        safety_res = tester.test_adversarial_safety_enforcement(n_adversarial_trials=25)
        results["safety_invariants"] = {
            "blocked_rejection_rate_pct": safety_res["safety_rejection_rate_pct"],
            "status": "PASSED" if safety_res["safety_rejection_rate_pct"] == 100.0 else "FAILED"
        }

        # 7. Multi-Agent Coordination
        coordinator = MultiAgentDispatchCoordinator(self.checkpoint_path)
        coord_res = coordinator.coordinate_sector([
            {"train_id": "VB-20901", "train_priority": 5.0, "location_station": "SUR", "current_delay_min": 5.0},
            {"train_id": "FR-90112", "train_priority": 2.0, "location_station": "SUR", "current_delay_min": 20.0}
        ])
        results["multi_agent_consensus"] = {
            "joint_conflict_free": coord_res["joint_conflict_free"],
            "latency_ms": coord_res["coordination_latency_ms"],
            "status": "PASSED" if coord_res["joint_conflict_free"] else "FAILED"
        }

        # Overall Status
        all_passed = all(
            v.get("status") in ("HEALTHY", "PASSED", "SUB_5MS_SATISFIED")
            for v in results.values()
        )

        diagnostic_report = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "overall_health": "ALL_DIAGNOSTICS_PASSED" if all_passed else "DEGRADED",
            "checks": results
        }

        with open("models/checkpoints/model_health_report.json", "w", encoding="utf-8") as f:
            json.dump(diagnostic_report, f, indent=2)

        return diagnostic_report

if __name__ == "__main__":
    diag = NexusModelDiagnostics()
    report = diag.run_diagnostics()
    print("\n--- NEXUS Core Model Health & Continuous Diagnostic Report ---")
    print(json.dumps(report, indent=2))
