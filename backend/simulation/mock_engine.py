import time
from typing import List, Dict, Any
from simulation.topology import STATIONS, RailTopology
from simulation.schedule import MOCK_SCHEDULES

# Topology wrapper for path calculation
topology = RailTopology()

def interpolate_coords(coord1: List[float], coord2: List[float], ratio: float) -> List[float]:
    """Linearly interpolate coordinates between two points."""
    lat = coord1[0] + (coord2[0] - coord1[0]) * ratio
    lon = coord1[1] + (coord2[1] - coord1[1]) * ratio
    return [lat, lon]

class MockSimulationEngine:
    """A lightweight time-based simulation engine for animating train movement on Day 1."""
    def __init__(self):
        self.start_real_time = time.time()
        self.sim_speed_multiplier = 30.0  # 1 real second = 30 simulated seconds (2 mins/sim minute)

    def get_sim_time_minutes(self) -> float:
        """Returns the elapsed simulated time in minutes since simulation start."""
        elapsed_real_seconds = time.time() - self.start_real_time
        return (elapsed_real_seconds * self.sim_speed_multiplier) / 60.0

    def get_active_trains(self) -> List[Dict[str, Any]]:
        """Calculate and return the current spatial status of all trains."""
        sim_time_mins = self.get_sim_time_minutes()
        active_trains = []

        for schedule in MOCK_SCHEDULES:
            dep_time = schedule["departure_time_mins"]
            
            # If the train has not departed yet, place it at the origin station
            if sim_time_mins < dep_time:
                origin_station = schedule["stops"][0]
                coords = STATIONS[origin_station]["coords"]
                active_trains.append({
                    "train_id": schedule["train_id"],
                    "service_type": schedule["service_type"],
                    "direction": schedule["direction"],
                    "current_node": origin_station,
                    "next_node": schedule["stops"][1] if len(schedule["stops"]) > 1 else origin_station,
                    "speed_kmh": 0.0,
                    "delay_minutes": 0.0,
                    "passenger_count": schedule["passenger_count"],
                    "coordinates": coords,
                    "status": "WAITING"
                })
                continue

            # Compute route traversal path
            stops = schedule["stops"]
            
            # Estimate where the train is on its path
            accumulated_time = dep_time
            current_stop_idx = 0
            in_transit = False
            ratio = 0.0
            from_node = stops[0]
            to_node = stops[0]

            # Traverse the route links to find the active block
            for i in range(len(stops) - 1):
                u, v = stops[i], stops[i+1]
                edge_data = topology.graph.get_edge_data(u, v)
                if not edge_data:
                    continue

                travel_time = edge_data["travel_time_min"]
                dwell_time = STATIONS[u]["base_dwell_time"]

                # Check if train is dwelling at station u
                if accumulated_time <= sim_time_mins < (accumulated_time + dwell_time):
                    from_node = u
                    to_node = u
                    ratio = 0.0
                    in_transit = False
                    break

                accumulated_time += dwell_time

                # Check if train is traveling on link (u, v)
                if accumulated_time <= sim_time_mins < (accumulated_time + travel_time):
                    from_node = u
                    to_node = v
                    ratio = (sim_time_mins - accumulated_time) / travel_time
                    in_transit = True
                    break

                accumulated_time += travel_time
                current_stop_idx = i + 1

            # If train has completed the full run, hold it at final destination
            if sim_time_mins >= accumulated_time:
                dest_station = stops[-1]
                coords = STATIONS[dest_station]["coords"]
                active_trains.append({
                    "train_id": schedule["train_id"],
                    "service_type": schedule["service_type"],
                    "direction": schedule["direction"],
                    "current_node": dest_station,
                    "next_node": dest_station,
                    "speed_kmh": 0.0,
                    "delay_minutes": 0.0,
                    "passenger_count": schedule["passenger_count"],
                    "coordinates": coords,
                    "status": "TERMINATED"
                })
                continue

            # Calculate live coordinate position
            if in_transit:
                coords1 = STATIONS[from_node]["coords"]
                coords2 = STATIONS[to_node]["coords"]
                coords = interpolate_coords(coords1, coords2, ratio)
                speed = 270.0  # Normal operational speed
                status = "RUNNING"
            else:
                coords = STATIONS[from_node]["coords"]
                speed = 0.0
                status = "DWELLING"

            active_trains.append({
                "train_id": schedule["train_id"],
                "service_type": schedule["service_type"],
                "direction": schedule["direction"],
                "current_node": from_node,
                "next_node": to_node,
                "speed_kmh": speed,
                "delay_minutes": 0.0,
                "passenger_count": schedule["passenger_count"],
                "coordinates": coords,
                "status": status
            })

        return active_trains
