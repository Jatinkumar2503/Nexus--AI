import networkx as nx
from typing import Dict, Any, List

# Mumbai-Ahmedabad High-Speed Rail Corridor (MAHSR) - Bullet Train India
# Coordinates: [Latitude, Longitude]
STATIONS: Dict[str, Dict[str, Any]] = {
    "MUM": {"name": "Mumbai BKC", "coords": [19.0601, 72.8601], "platforms": 6, "base_dwell_time": 3},
    "TNA": {"name": "Thane", "coords": [19.1860, 72.9734], "platforms": 4, "base_dwell_time": 2},
    "VIR": {"name": "Virar", "coords": [19.4564, 72.8122], "platforms": 2, "base_dwell_time": 1},
    "BOI": {"name": "Boisar", "coords": [19.8015, 72.7641], "platforms": 2, "base_dwell_time": 1},
    "VAP": {"name": "Vapi", "coords": [20.3756, 72.9067], "platforms": 2, "base_dwell_time": 1},
    "BIL": {"name": "Bilimora", "coords": [20.7816, 72.9644], "platforms": 2, "base_dwell_time": 1},
    "SUR": {"name": "Surat", "coords": [21.2044, 72.8406], "platforms": 4, "base_dwell_time": 2},
    "BHA": {"name": "Bharuch", "coords": [21.7107, 72.9972], "platforms": 2, "base_dwell_time": 1},
    "VAD": {"name": "Vadodara", "coords": [22.3129, 73.1812], "platforms": 4, "base_dwell_time": 2},
    "ANA": {"name": "Anand", "coords": [22.5645, 72.9498], "platforms": 2, "base_dwell_time": 1},
    "ADI": {"name": "Ahmedabad", "coords": [23.0276, 72.6022], "platforms": 6, "base_dwell_time": 3},
    "SAB": {"name": "Sabarmati", "coords": [23.0805, 72.5855], "platforms": 4, "base_dwell_time": 2}
}

class RailTopology:
    """Represents the static Indian rail network graph using NetworkX."""
    def __init__(self):
        self.graph = nx.DiGraph()
        self._load_nodes()
        self._load_edges()

    def _load_nodes(self):
        """Load stations as nodes in the graph, including slow-line detour nodes."""
        for code, info in STATIONS.items():
            self.graph.add_node(
                code,
                name=info["name"],
                coords=info["coords"],
                platforms=info["platforms"],
                base_dwell_time=info["base_dwell_time"]
            )
            # Add parallel slow-line node
            self.graph.add_node(
                f"{code}_SLOW",
                name=f"{info['name']} (Slow Line)",
                coords=[info["coords"][0] + 0.001, info["coords"][1] + 0.001],
                platforms=2,
                base_dwell_time=info["base_dwell_time"]
            )

    def _load_edges(self):
        """Load track segments as directional edges with distance and travel times, including slow lines."""
        sequence = ["MUM", "TNA", "VIR", "BOI", "VAP", "BIL", "SUR", "BHA", "VAD", "ANA", "ADI", "SAB"]
        
        segments = [
            ("MUM", "TNA", 28.0, 10),
            ("TNA", "VIR", 43.0, 12),
            ("VIR", "BOI", 40.0, 11),
            ("BOI", "VAP", 66.0, 15),
            ("VAP", "BIL", 47.0, 12),
            ("BIL", "SUR", 50.0, 12),
            ("SUR", "BHA", 60.0, 14),
            ("BHA", "VAD", 80.0, 17),
            ("VAD", "ANA", 32.0, 10),
            ("ANA", "ADI", 55.0, 13),
            ("ADI", "SAB", 7.0, 5)
        ]

        for u, v, dist, time in segments:
            # Main line edges
            self.graph.add_edge(u, v, distance_km=dist, travel_time_min=time, direction="outbound", status="open", is_slow=False)
            self.graph.add_edge(v, u, distance_km=dist, travel_time_min=time, direction="inbound", status="open", is_slow=False)
            
            # Slow line parallel detour edges (takes 1.5x travel time)
            slow_time = int(time * 1.5)
            self.graph.add_edge(f"{u}_SLOW", f"{v}_SLOW", distance_km=dist, travel_time_min=slow_time, direction="outbound", status="open", is_slow=True)
            self.graph.add_edge(f"{v}_SLOW", f"{u}_SLOW", distance_km=dist, travel_time_min=slow_time, direction="inbound", status="open", is_slow=True)

        # Connect main line to slow line switches at each station (1.5 min penalty)
        for code in STATIONS:
            self.graph.add_edge(code, f"{code}_SLOW", distance_km=0.5, travel_time_min=1.5, direction="switch", status="open", is_slow=True)
            self.graph.add_edge(f"{code}_SLOW", code, distance_km=0.5, travel_time_min=1.5, direction="switch", status="open", is_slow=True)

    def get_nodes(self) -> Dict[str, Dict[str, Any]]:
        """Return all station nodes with their attributes."""
        return {node: self.graph.nodes[node] for node in self.graph.nodes}

    def get_edges(self) -> List[Dict[str, Any]]:
        """Return all track segments (edges) in the graph."""
        edges = []
        for u, v, data in self.graph.edges(data=True):
            edges.append({
                "from_node": u,
                "to_node": v,
                "distance_km": data["distance_km"],
                "travel_time_min": data["travel_time_min"],
                "direction": data["direction"],
                "status": data["status"]
            })
        return edges

    def get_path(self, origin: str, destination: str, blocked_edges: List[str] = None) -> List[str]:
        """Compute the shortest path between stations using Dijkstra, optionally avoiding blocked edges."""
        if not blocked_edges:
            try:
                return nx.shortest_path(self.graph, source=origin, target=destination, weight="travel_time_min")
            except (nx.NetworkXNoPath, nx.NodeNotFound):
                return []
        
        # Create a temporary graph copy to avoid modifying global network state
        temp_graph = self.graph.copy()
        for edge in blocked_edges:
            if "->" in edge:
                u, v = edge.split("->")
                if temp_graph.has_edge(u, v):
                    temp_graph[u][v]["travel_time_min"] = 9999.0
            else:
                # Node blockage: block all incident edges
                for neighbor in list(temp_graph.neighbors(edge)):
                    temp_graph[edge][neighbor]["travel_time_min"] = 9999.0
                    temp_graph[neighbor][edge]["travel_time_min"] = 9999.0
        try:
            return nx.shortest_path(temp_graph, source=origin, target=destination, weight="travel_time_min")
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return []
