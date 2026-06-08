import networkx as nx
from typing import Dict, Any, List

# Tokaido Shinkansen Stations (Tokyo to Shin-Osaka)
# Coordinates: [Latitude, Longitude]
STATIONS: Dict[str, Dict[str, Any]] = {
    "TYO": {"name": "Tokyo", "coords": [35.681236, 139.767125], "platforms": 6, "base_dwell_time": 2},
    "SYO": {"name": "Shin-Yokohama", "coords": [35.507456, 139.617585], "platforms": 4, "base_dwell_time": 1},
    "ODW": {"name": "Odawara", "coords": [35.256139, 139.154944], "platforms": 2, "base_dwell_time": 1},
    "ATM": {"name": "Atami", "coords": [35.103722, 139.077694], "platforms": 2, "base_dwell_time": 1},
    "MSM": {"name": "Mishima", "coords": [35.127083, 138.910833], "platforms": 3, "base_dwell_time": 1},
    "SFJ": {"name": "Shin-Fuji", "coords": [35.142222, 138.662778], "platforms": 2, "base_dwell_time": 1},
    "SZO": {"name": "Shizuoka", "coords": [34.971667, 138.388889], "platforms": 4, "base_dwell_time": 1.5},
    "KKG": {"name": "Kakegawa", "coords": [34.769444, 138.015], "platforms": 2, "base_dwell_time": 1},
    "HMM": {"name": "Hamamatsu", "coords": [34.703611, 137.734722], "platforms": 4, "base_dwell_time": 1.5},
    "TYH": {"name": "Toyohashi", "coords": [34.762778, 137.381944], "platforms": 3, "base_dwell_time": 1},
    "MKA": {"name": "Mikawa-Anjo", "coords": [34.966944, 137.061389], "platforms": 2, "base_dwell_time": 1},
    "NGO": {"name": "Nagoya", "coords": [35.170915, 136.881537], "platforms": 4, "base_dwell_time": 2},
    "GFH": {"name": "Gifu-Hashima", "coords": [35.315833, 136.685833], "platforms": 2, "base_dwell_time": 1},
    "MBR": {"name": "Maibara", "coords": [35.314444, 136.290278], "platforms": 3, "base_dwell_time": 1},
    "KYT": {"name": "Kyoto", "coords": [34.985849, 135.758767], "platforms": 4, "base_dwell_time": 2},
    "OSA": {"name": "Shin-Osaka", "coords": [34.73348, 135.500109], "platforms": 6, "base_dwell_time": 3}
}

class RailTopology:
    """Represents the static rail network graph using NetworkX."""
    def __init__(self):
        self.graph = nx.DiGraph()
        self._load_nodes()
        self._load_edges()

    def _load_nodes(self):
        """Load Shinkansen stations as nodes in the graph."""
        for code, info in STATIONS.items():
            self.graph.add_node(
                code,
                name=info["name"],
                coords=info["coords"],
                platforms=info["platforms"],
                base_dwell_time=info["base_dwell_time"]
            )

    def _load_edges(self):
        """Load Shinkansen track segments as directional edges with distance and travel times."""
        # Sequence of stations from Tokyo to Shin-Osaka
        sequence = ["TYO", "SYO", "ODW", "ATM", "MSM", "SFJ", "SZO", "KKG", "HMM", "TYH", "MKA", "NGO", "GFH", "MBR", "KYT", "OSA"]
        
        # Link distances (km) and estimated travel times (minutes) under normal operating speeds (~250-285 km/h)
        segments = [
            ("TYO", "SYO", 25.5, 11),
            ("SYO", "ODW", 50.8, 16),
            ("ODW", "ATM", 20.7, 8),
            ("ATM", "MSM", 11.6, 6),
            ("MSM", "SFJ", 20.6, 7),
            ("SFJ", "SZO", 31.7, 10),
            ("SZO", "KKG", 40.2, 12),
            ("KKG", "HMM", 29.3, 9),
            ("HMM", "TYH", 28.9, 9),
            ("TYH", "MKA", 38.6, 11),
            ("MKA", "NGO", 22.0, 9),
            ("NGO", "GFH", 24.2, 9),
            ("GFH", "MBR", 37.1, 11),
            ("MBR", "KYT", 67.7, 19),
            ("KYT", "OSA", 39.0, 12)
        ]

        for u, v, dist, time in segments:
            # Outbound direction (Tokyo -> Shin-Osaka)
            self.graph.add_edge(u, v, distance_km=dist, travel_time_min=time, direction="outbound", status="open")
            # Inbound direction (Shin-Osaka -> Tokyo)
            self.graph.add_edge(v, u, distance_km=dist, travel_time_min=time, direction="inbound", status="open")

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

    def get_path(self, origin: str, destination: str) -> List[str]:
        """Compute the shortest path between stations using Dijkstra."""
        try:
            return nx.shortest_path(self.graph, source=origin, target=destination, weight="travel_time_min")
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return []

