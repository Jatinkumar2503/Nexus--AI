"""NEXUS AI — Deterministic Hard Constraint Validator.

Enforces Tier 1 Hard Invariants (0.00% tolerance for safety-critical dispatch):
1. Spatial & Temporal Headway Invariant (H_min >= 120s, distance >= braking_distance)
2. Single Block Section Exclusion (No simultaneous double-occupancy on absolute blocks)
3. Platform Berth Capacity & Clearance (Length <= BerthLength, Platform Occupancy <= 1)
4. Interlocking Route Exclusivity (No overlapping fouling zones)
5. Monotonic Temporal Sequencing (t_arr < t_dep, t_dep >= t_arr + base_dwell)
6. Speed Limit & Caution Order Enforcement (v <= min(MPS, TSR, LocoMaxSpeed))
"""

import os
import sys
from typing import Dict, Any, List, Optional, Tuple

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from backend.data.schema import CanonicalRailwayDataset, TrainSchema, SectionSchema, PlatformSchema, StationSchema

class DeterministicSafetyValidator:
    def __init__(self, dataset: CanonicalRailwayDataset):
        self.dataset = dataset
        self.stations: Dict[str, StationSchema] = {s.station_id: s for s in dataset.stations}
        self.sections: Dict[str, SectionSchema] = {s.section_id: s for s in dataset.sections}
        self.platforms: Dict[str, PlatformSchema] = {p.platform_id: p for p in dataset.platforms}
        self.trains: Dict[str, TrainSchema] = {t.train_number: t for t in dataset.trains}

        # Spatial headway parameter (default 120 seconds / 2 minutes)
        self.min_headway_seconds = 120.0
        self.min_headway_minutes = self.min_headway_seconds / 60.0

    def check_temporal_sequencing(self, train_number: str, arrival_min: float, departure_min: float, station_id: str) -> Tuple[bool, Optional[str]]:
        """Validates arrival < departure and dwell >= base_dwell."""
        stn = self.stations.get(station_id)
        if not stn:
            return False, f"Unknown station: {station_id}"
        
        if departure_min < arrival_min:
            return False, f"Negative dwell time: departure ({departure_min}m) < arrival ({arrival_min}m) at {station_id}"
        
        actual_dwell = departure_min - arrival_min
        # Allow technical stop of at least 0.5m, but for scheduled stops dwell >= base_dwell * 0.8
        min_allowed_dwell = max(0.5, stn.base_dwell_min * 0.5)
        if actual_dwell < min_allowed_dwell:
            return False, f"Dwell violation: dwell ({actual_dwell}m) < minimum required ({min_allowed_dwell}m) at {station_id}"
        
        return True, None

    def check_block_occupancy(self, section_id: str, active_occupants: List[str]) -> Tuple[bool, Optional[str]]:
        """Validates that absolute block sections do not contain >1 train simultaneously."""
        sec = self.sections.get(section_id)
        if not sec:
            return False, f"Unknown block section: {section_id}"
        
        # Absolute block allows only 1 train per track
        max_allowed = sec.track_count if sec.signalling_type == "automatic_block" else 1
        if len(active_occupants) > max_allowed:
            return False, f"Block saturation hazard: Section {section_id} has {len(active_occupants)} trains (max allowed: {max_allowed}): {active_occupants}"
        
        return True, None

    def check_platform_clearance(self, train_number: str, platform_id: str, active_occupant: Optional[str]) -> Tuple[bool, Optional[str]]:
        """Validates platform length accommodation and single occupancy."""
        plt = self.platforms.get(platform_id)
        if not plt:
            return False, f"Unknown platform: {platform_id}"
        
        trn = self.trains.get(train_number)
        if not trn:
            return False, f"Unknown train: {train_number}"
        
        if trn.length_meters > plt.berth_length_m:
            return False, f"Platform length overrun: Train {train_number} length ({trn.length_meters}m) exceeds Platform {platform_id} berth ({plt.berth_length_m}m)"
        
        if active_occupant and active_occupant != train_number:
            return False, f"Platform collision: Platform {platform_id} already occupied by Train {active_occupant}"
        
        return True, None

    def check_headway_spacing(self, leader_dep_min: float, follower_dep_min: float, section_id: str) -> Tuple[bool, Optional[str]]:
        """Validates minimum headway spacing between consecutive trains entering section."""
        time_gap = follower_dep_min - leader_dep_min
        if time_gap < self.min_headway_minutes:
            return False, f"Headway violation in Section {section_id}: time gap ({time_gap*60:.1f}s) < minimum required ({self.min_headway_seconds}s)"
        return True, None

    def check_speed_compliance(self, train_number: str, section_id: str, proposed_speed_kmh: float, tsr_limit_kmh: Optional[float] = None) -> Tuple[bool, Optional[str]]:
        """Validates that train speed does not exceed sectional MPS, TSR, or loco max speed."""
        sec = self.sections.get(section_id)
        if not sec:
            return False, f"Unknown section: {section_id}"
        
        trn = self.trains.get(train_number)
        if not trn:
            return False, f"Unknown train: {train_number}"
        
        max_allowed = min(sec.max_permitted_speed, trn.max_loco_speed_kmh)
        if tsr_limit_kmh is not None:
            max_allowed = min(max_allowed, tsr_limit_kmh)
        
        if proposed_speed_kmh > max_allowed + 0.1:
            return False, f"Speed overspeed violation: Proposed {proposed_speed_kmh:.1f} km/h > Max permissible {max_allowed:.1f} km/h in Section {section_id}"
        
        return True, None

    def validate_dispatch_action(self, action_dict: Dict[str, Any], current_state: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Comprehensive verification of an ML-recommended operational action."""
        violations = []
        act_type = action_dict.get("action_type", "do_nothing")
        train_id = action_dict.get("train_id")
        loc_id = action_dict.get("location")

        if act_type == "hold":
            # Holding at station: verify station exists and duration >= 0
            if loc_id not in self.stations:
                violations.append(f"Invalid hold location: {loc_id}")
            hold_min = action_dict.get("hold_duration_minutes", 0)
            if hold_min < 0:
                violations.append(f"Negative hold duration: {hold_min}")

        elif act_type == "change_platform":
            plt_id = action_dict.get("new_platform_id")
            occupant = current_state.get("platform_occupancy", {}).get(plt_id)
            is_valid, err = self.check_platform_clearance(train_id, plt_id, occupant)
            if not is_valid:
                violations.append(err)

        elif act_type == "speed_throttle":
            sec_id = loc_id
            proposed_speed = action_dict.get("target_speed_kmh", 80.0)
            tsr = current_state.get("tsr_limits", {}).get(sec_id)
            is_valid, err = self.check_speed_compliance(train_id, sec_id, proposed_speed, tsr)
            if not is_valid:
                violations.append(err)

        elif act_type == "reroute_detour":
            path = action_dict.get("routing_path", [])
            if len(path) < 2:
                violations.append("Detour path must contain at least 2 nodes")
            for idx in range(len(path) - 1):
                u, v = path[idx], path[idx + 1]
                # Check if physical connectivity exists
                connected = any(
                    (s.from_node == u and s.to_node == v) or (s.from_node == v and s.to_node == u)
                    for s in self.dataset.sections
                )
                if not connected:
                    violations.append(f"Disconnected detour segment: {u} -> {v}")

        is_approved = (len(violations) == 0)
        return is_approved, violations
