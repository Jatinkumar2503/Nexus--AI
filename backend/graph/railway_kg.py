"""NEXUS AI — Heterogeneous Railway Knowledge Graph Engine.

Constructs dynamic heterogeneous multigraphs G_t = (V, E, X_t) from canonical railway datasets:
- Nodes: Station (V_stn), Section (V_sec), Train (V_trn), Platform (V_plt)
- Edges: CONNECTS_TO, IN_STATION, OCCUPIES_SEC, OCCUPIES_PLT, ROUTES_THROUGH, PRECEDES, CONFLICTS_WITH
- Exports PyTorch Geometric HeteroData layout and computes topological invariants.
"""

import os
import sys
import networkx as nx
import numpy as np
from typing import Dict, Any, List, Optional, Tuple

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from backend.data.schema import CanonicalRailwayDataset

class RailwayKnowledgeGraph:
    def __init__(self, dataset: Optional[CanonicalRailwayDataset] = None):
        self.dataset = dataset
        self.graph = nx.MultiDiGraph()
        self.station_indices: Dict[str, int] = {}
        self.section_indices: Dict[str, int] = {}
        self.train_indices: Dict[str, int] = {}
        self.platform_indices: Dict[str, int] = {}
        
        if self.dataset:
            self.build_graph(self.dataset)

    def build_graph(self, dataset: CanonicalRailwayDataset):
        """Constructs the heterogeneous railway knowledge graph."""
        self.dataset = dataset
        self.graph.clear()
        self.station_indices.clear()
        self.section_indices.clear()
        self.train_indices.clear()
        self.platform_indices.clear()

        # 1. Add Station Nodes (V_stn)
        for idx, stn in enumerate(dataset.stations):
            self.station_indices[stn.station_id] = idx
            # Feature vector: [lat_norm, lon_norm, pf_norm, is_junc, is_term, dwell_norm, active_trains, avail_pfs, yard_cong, elev_norm]
            features = np.array([
                stn.latitude / 90.0,
                stn.longitude / 180.0,
                stn.platform_count / 24.0,
                1.0 if stn.is_junction else 0.0,
                1.0 if stn.is_terminal else 0.0,
                stn.base_dwell_min / 30.0,
                0.0,  # dynamic active trains in station
                stn.platform_count / 24.0,  # dynamic available platforms
                0.0,  # dynamic yard congestion ratio
                (stn.elevation_m or 0.0) / 500.0
            ], dtype=np.float32)

            self.graph.add_node(
                stn.station_id,
                node_type="station",
                entity_id=stn.station_id,
                name=stn.name,
                features=features,
                raw_data=stn.model_dump()
            )

        # 2. Add Platform Nodes (V_plt) & IN_STATION Edges
        for idx, plt in enumerate(dataset.platforms):
            self.platform_indices[plt.platform_id] = idx
            features = np.array([
                plt.platform_number / 24.0,
                plt.berth_length_m / 800.0,
                0.0,  # is_occupied
                1.0 if plt.is_electrified else 0.0,
                0.0   # time_until_free_min
            ], dtype=np.float32)

            self.graph.add_node(
                plt.platform_id,
                node_type="platform",
                entity_id=plt.platform_id,
                features=features,
                raw_data=plt.model_dump()
            )

            # Platform -> Station edge
            self.graph.add_edge(
                plt.platform_id,
                plt.station_id,
                edge_type="in_station",
                platform_number=plt.platform_number
            )

        # 3. Add Block Section Nodes (V_sec) & CONNECTS_TO Edges
        for idx, sec in enumerate(dataset.sections):
            self.section_indices[sec.section_id] = idx
            features = np.array([
                sec.length_km / 100.0,
                sec.max_permitted_speed / 200.0,
                sec.gradient_permille / 30.0,
                1.0 if sec.is_electrified else 0.0,
                sec.track_count / 4.0,
                0.0,  # signal aspect: 0=Green, 1=Double Yellow, 2=Yellow, 3=Red
                0.0,  # active occupancy flag
                sec.max_permitted_speed / 200.0,  # temporary speed restriction
                1.0 if sec.direction == "outbound" else 0.0
            ], dtype=np.float32)

            self.graph.add_node(
                sec.section_id,
                node_type="section",
                entity_id=sec.section_id,
                features=features,
                raw_data=sec.model_dump()
            )

            # Station -> Section & Section -> Station physical connectivity
            self.graph.add_edge(
                sec.from_node,
                sec.section_id,
                edge_type="connects_to",
                distance_km=sec.length_km,
                mps=sec.max_permitted_speed
            )
            self.graph.add_edge(
                sec.section_id,
                sec.to_node,
                edge_type="connects_to",
                distance_km=sec.length_km,
                mps=sec.max_permitted_speed
            )

        # 4. Add Train Nodes (V_trn) & ROUTES_THROUGH Edges
        category_map = {"vande_bharat": 0, "rajdhani_shatabdi": 1, "superfast": 2, "mail_express": 3, "passenger_local": 4, "freight_container": 5, "freight_bulk": 6}
        for idx, trn in enumerate(dataset.trains):
            self.train_indices[trn.train_number] = idx
            cat_val = category_map.get(trn.category, 3)
            features = np.array([
                trn.priority_weight / 5.0,
                cat_val / 6.0,
                trn.length_meters / 800.0,
                trn.trailing_tonnage / 8000.0,
                trn.max_loco_speed_kmh / 200.0,
                0.0,  # current_speed
                0.0,  # cumulative_delay_min
                trn.passenger_capacity / 2500.0,
                1.0,  # remaining_distance_norm
                10.0 / 10.0,  # crew_duty_hours_left
                1.0   # traction: 1.0 = Electric
            ], dtype=np.float32)

            self.graph.add_node(
                trn.train_number,
                node_type="train",
                entity_id=trn.train_number,
                features=features,
                raw_data=trn.model_dump()
            )

            # Train -> Station Scheduled Itinerary Edges (ROUTES_THROUGH)
            for stop in trn.timetable:
                self.graph.add_edge(
                    trn.train_number,
                    stop.station_id,
                    edge_type="routes_through",
                    sched_arr=stop.scheduled_arrival_min,
                    sched_dep=stop.scheduled_departure_min,
                    sched_dwell=stop.scheduled_dwell_min
                )

    def update_train_dynamic_state(self, train_number: str, current_sec: Optional[str], current_plt: Optional[str], speed_kmh: float, delay_min: float):
        """Updates dynamic node features and spatial occupancy edges."""
        if train_number not in self.graph.nodes:
            return
        
        # Remove prior dynamic occupancy edges for this train
        to_remove = []
        for u, v, k, data in self.graph.edges(train_number, keys=True, data=True):
            if data.get("edge_type") in ("occupies_sec", "occupies_plt"):
                to_remove.append((u, v, k))
        for u, v, k in to_remove:
            self.graph.remove_edge(u, v, key=k)

        # Update train node features
        node = self.graph.nodes[train_number]
        feat = node["features"]
        feat[5] = speed_kmh / 200.0
        feat[6] = delay_min / 360.0

        # Add active occupancy edge
        if current_sec and current_sec in self.graph.nodes:
            self.graph.add_edge(train_number, current_sec, edge_type="occupies_sec", speed_kmh=speed_kmh, delay_min=delay_min)
            # Mark section occupied
            self.graph.nodes[current_sec]["features"][6] = 1.0

        if current_plt and current_plt in self.graph.nodes:
            self.graph.add_edge(train_number, current_plt, edge_type="occupies_plt", berth_time=0.0)
            # Mark platform occupied
            self.graph.nodes[current_plt]["features"][2] = 1.0

    def add_precedence_and_conflict_edges(self, precedences: List[Tuple[str, str, float]], conflicts: List[Tuple[str, str, str]]):
        """Adds dynamic PRECEDES and CONFLICTS_WITH edges between train pairs."""
        for leader, follower, gap_sec in precedences:
            if leader in self.graph.nodes and follower in self.graph.nodes:
                self.graph.add_edge(leader, follower, edge_type="precedes", headway_gap_sec=gap_sec)

        for trn_a, trn_b, conflict_type in conflicts:
            if trn_a in self.graph.nodes and trn_b in self.graph.nodes:
                self.graph.add_edge(trn_a, trn_b, edge_type="conflicts_with", conflict_type=conflict_type)
                self.graph.add_edge(trn_b, trn_a, edge_type="conflicts_with", conflict_type=conflict_type)

    def validate_topological_invariants(self) -> Tuple[bool, List[str]]:
        """Verifies mathematical and operational graph invariants."""
        errors = []

        # 1. Station connectivity
        stn_nodes = [n for n, d in self.graph.nodes(data=True) if d.get("node_type") == "station"]
        if len(stn_nodes) < 2:
            errors.append("Graph contains fewer than 2 stations.")

        # 2. Block section connections
        sec_nodes = [n for n, d in self.graph.nodes(data=True) if d.get("node_type") == "section"]
        for sec in sec_nodes:
            in_edges = [u for u, v, d in self.graph.in_edges(sec, data=True) if d.get("edge_type") == "connects_to"]
            out_edges = [v for u, v, d in self.graph.out_edges(sec, data=True) if d.get("edge_type") == "connects_to"]
            if not in_edges or not out_edges:
                errors.append(f"Section {sec} is dangling (missing station endpoints).")

        # 3. Single-occupancy invariant check on block sections
        for sec in sec_nodes:
            occupants = [u for u, v, d in self.graph.in_edges(sec, data=True) if d.get("edge_type") == "occupies_sec"]
            if len(occupants) > 1:
                errors.append(f"Hard Invariant Violation: Section {sec} occupied simultaneously by {len(occupants)} trains: {occupants}")

        return (len(errors) == 0), errors

    def to_tensor_dict(self) -> Dict[str, Any]:
        """Converts graph into canonical tensor layout for neural model consumption."""
        stn_nodes = [n for n, d in self.graph.nodes(data=True) if d.get("node_type") == "station"]
        sec_nodes = [n for n, d in self.graph.nodes(data=True) if d.get("node_type") == "section"]
        trn_nodes = [n for n, d in self.graph.nodes(data=True) if d.get("node_type") == "train"]
        plt_nodes = [n for n, d in self.graph.nodes(data=True) if d.get("node_type") == "platform"]

        x_stn = np.stack([self.graph.nodes[n]["features"] for n in stn_nodes]) if stn_nodes else np.empty((0, 10))
        x_sec = np.stack([self.graph.nodes[n]["features"] for n in sec_nodes]) if sec_nodes else np.empty((0, 9))
        x_trn = np.stack([self.graph.nodes[n]["features"] for n in trn_nodes]) if trn_nodes else np.empty((0, 11))
        x_plt = np.stack([self.graph.nodes[n]["features"] for n in plt_nodes]) if plt_nodes else np.empty((0, 5))

        # Build edge index matrices
        def get_edge_index(edge_type_filter: str, src_dict: Dict[str, int], dst_dict: Dict[str, int]) -> np.ndarray:
            srcs, dsts = [], []
            for u, v, d in self.graph.edges(data=True):
                if d.get("edge_type") == edge_type_filter and u in src_dict and v in dst_dict:
                    srcs.append(src_dict[u])
                    dsts.append(dst_dict[v])
            if not srcs:
                return np.empty((2, 0), dtype=np.int64)
            return np.array([srcs, dsts], dtype=np.int64)

        return {
            "x_dict": {
                "station": x_stn,
                "section": x_sec,
                "train": x_trn,
                "platform": x_plt
            },
            "edge_index_dict": {
                ("station", "connects_to", "section"): get_edge_index("connects_to", self.station_indices, self.section_indices),
                ("section", "connects_to", "station"): get_edge_index("connects_to", self.section_indices, self.station_indices),
                ("platform", "in_station", "station"): get_edge_index("in_station", self.platform_indices, self.station_indices),
                ("train", "occupies_sec", "section"): get_edge_index("occupies_sec", self.train_indices, self.section_indices),
                ("train", "occupies_plt", "platform"): get_edge_index("occupies_plt", self.train_indices, self.platform_indices),
                ("train", "routes_through", "station"): get_edge_index("routes_through", self.train_indices, self.station_indices),
                ("train", "precedes", "train"): get_edge_index("precedes", self.train_indices, self.train_indices),
                ("train", "conflicts_with", "train"): get_edge_index("conflicts_with", self.train_indices, self.train_indices)
            },
            "num_nodes_dict": {
                "station": len(stn_nodes),
                "section": len(sec_nodes),
                "train": len(trn_nodes),
                "platform": len(plt_nodes)
            }
        }
