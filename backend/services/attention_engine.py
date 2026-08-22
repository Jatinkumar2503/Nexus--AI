"""NEXUS AI — Attention Management & Context-Aware Default Behavior Engine.

Addresses Focus Prioritization, Interruption Triage, Cognitive Review Load Index (CRLI),
and Context-Aware Sensible Parameter Defaults while keeping all parameters 100% editable.
"""

import math
import time
from typing import Dict, Any, List, Optional

class AttentionEngine:
    def __init__(self):
        # Default editable settings (100% customizable by dispatchers via API/UI)
        self.settings = {
            "auto_approve_confidence_threshold": 85.0,  # % model confidence required for auto-approval
            "interruption_sensitivity": "BALANCED",     # LOW, BALANCED, HIGH
            "batch_review_interval_sec": 30,           # Notification batching window
            "max_batch_size": 5,                       # Max advisories per batch
            "crli_overload_threshold": 75.0,            # CRLI score triggering automatic quiet mode
            "enable_auto_approval": True,
            "enable_smart_prefill": True,
        }
        self.pending_batch_queue: List[Dict[str, Any]] = []
        self.last_batch_flush_time = time.time()

    def calculate_crli(
        self,
        active_disruptions_count: int,
        pending_review_count: int,
        active_train_density: int,
        average_uncertainty_spread: float = 1.0
    ) -> Dict[str, Any]:
        """Calculates the Cognitive Review Load Index (CRLI) on a 0-100 scale."""
        disruption_weight = min(40.0, active_disruptions_count * 12.5)
        queue_weight = min(35.0, pending_review_count * 7.0)
        density_weight = min(15.0, (active_train_density / 20.0) * 15.0)
        uncertainty_weight = min(10.0, average_uncertainty_spread * 5.0)

        raw_score = disruption_weight + queue_weight + density_weight + uncertainty_weight
        crli_score = min(100.0, max(0.0, round(raw_score, 1)))

        if crli_score < 35.0:
            load_state = "QUIET"
            recommendation = "Normal operations. Full manual review capability active."
        elif crli_score < 75.0:
            load_state = "FOCUSED"
            recommendation = "Moderate operational load. Routine advisories batched."
        else:
            load_state = "OVERLOAD"
            recommendation = "High cognitive pressure detected. Auto-approving high-confidence actions (>85%) to protect focus."

        return {
            "crli_score": crli_score,
            "load_state": load_state,
            "recommendation": recommendation,
            "components": {
                "disruption_load": round(disruption_weight, 1),
                "queue_load": round(queue_weight, 1),
                "density_load": round(density_weight, 1),
                "uncertainty_load": round(uncertainty_weight, 1)
            }
        }

    def derive_context_defaults(
        self,
        input_state: Dict[str, Any],
        model_prediction: Optional[Dict[str, Any]] = None,
        historical_memory: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """Calculates sensible default parameters for recovery plans based on operational context."""
        current_delay = input_state.get("current_delay_min", 0.0)
        is_fog = input_state.get("weather") == "dense_fog"
        train_priority = input_state.get("train_priority", 3.0)

        # 1. Default Hold Duration Calculation
        if is_fog:
            base_hold = math.ceil(current_delay * 0.4) + 2
        else:
            base_hold = math.ceil(current_delay * 0.3)
        default_hold_duration = max(2, min(20, base_hold))

        # 2. Default Platform Preference
        default_platform = f"PF_{(int(train_priority) % 4) + 1}"

        # 3. Default Detour Path Selection
        if current_delay > 15.0:
            default_route = "FAST_LINE_BYPASS"
            route_rationale = "Severe delay (>15m) detected: routing via Fast-Line detour."
        else:
            default_route = "MAIN_CORRIDOR"
            route_rationale = "Minor delay: maintaining scheduled Main Corridor path."

        # 4. Default Speed Restriction
        default_speed_kmh = 45.0 if is_fog else (110.0 if train_priority >= 4.0 else 90.0)

        # Rationale summary for human transparency
        rationale = [
            f"Hold duration ({default_hold_duration}m) derived from accumulated delay ({current_delay}m) and weather state.",
            route_rationale,
            f"Platform {default_platform} assigned based on train priority rank ({train_priority}/5)."
        ]

        return {
            "defaults": {
                "hold_duration_min": default_hold_duration,
                "recommended_platform": default_platform,
                "detour_route": default_route,
                "target_speed_kmh": default_speed_kmh,
                "precedence_swap": train_priority >= 4.0
            },
            "is_editable": True,
            "rationale": rationale,
            "derived_from_context": {
                "delay_severity": "HIGH" if current_delay > 15 else "MODERATE",
                "weather_impact": "FOG_HEADWAY_BUFFER" if is_fog else "STANDARD",
                "priority_weight": train_priority
            }
        }

    def triage_interruption(
        self,
        event_type: str,
        model_confidence_pct: float,
        safety_violations_count: int = 0,
        is_ood: bool = False
    ) -> Dict[str, Any]:
        """Categorizes incoming events into QUIET_AUTO_EXECUTE, BATCH_REVIEW, or IMMEDIATE_INTERRUPT."""
        threshold = self.settings["auto_approve_confidence_threshold"]
        sensitivity = self.settings["interruption_sensitivity"]

        # Sensitivity offset adjustments
        if sensitivity == "HIGH":
            threshold += 5.0
        elif sensitivity == "LOW":
            threshold -= 5.0

        # High Hazard / Safety Violation / OOD -> Immediate Interruption
        if safety_violations_count > 0 or is_ood or event_type in ["SIGNAL_FAILURE", "SUBSTATION_TRIP"]:
            triage_category = "IMMEDIATE_INTERRUPT"
            action_required = "CRITICAL: Immediate dispatcher focus required on map."
            badge_color = "RED"
        # High Confidence + Safe + Auto-Approve Enabled -> Quiet Auto Execute
        elif self.settings["enable_auto_approval"] and model_confidence_pct >= threshold and safety_violations_count == 0:
            triage_category = "QUIET_AUTO_EXECUTE"
            action_required = "Auto-approved with quiet audit log entry."
            badge_color = "GREEN"
        # Default / Medium Impact -> Batch Review
        else:
            triage_category = "BATCH_REVIEW"
            action_required = "Added to low-interruption batch review queue."
            badge_color = "AMBER"

        return {
            "triage_category": triage_category,
            "model_confidence_pct": round(model_confidence_pct, 1),
            "applied_threshold_pct": threshold,
            "action_required": action_required,
            "badge_color": badge_color,
            "is_auto_approved": triage_category == "QUIET_AUTO_EXECUTE"
        }

    def update_settings(self, new_settings: Dict[str, Any]) -> Dict[str, Any]:
        """Updates editable threshold settings."""
        for key, val in new_settings.items():
            if key in self.settings:
                self.settings[key] = val
        return {"status": "SUCCESS", "settings": self.settings}

# Global singleton instance
attention_engine = AttentionEngine()
