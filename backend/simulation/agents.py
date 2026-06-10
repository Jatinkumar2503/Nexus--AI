import simpy
from typing import List, Dict, Any, Optional

def interpolate_coords(coord1: List[float], coord2: List[float], ratio: float) -> List[float]:
    """Linearly interpolate coordinates between two points [lat, lon]."""
    lat = coord1[0] + (coord2[0] - coord1[0]) * ratio
    lon = coord1[1] + (coord2[1] - coord1[1]) * ratio
    return [lat, lon]

class CrewAgent:
    """Crew Agent to monitor shift constraints and roster violations."""
    def __init__(self, crew_id: str, train_id: str, shift_start_mins: float = 0.0):
        self.crew_id = crew_id
        self.train_id = train_id
        self.shift_start_mins = shift_start_mins
        self.max_shift_duration_mins = 480.0  # 8 hours standard shift
        self.violated = False
        self.shift_end_mins = self.shift_start_mins + self.max_shift_duration_mins

    def check_violation(self, current_time_mins: float, estimated_remaining_mins: float) -> bool:
        """Check if the predicted arrival time exceeds the maximum shift duration."""
        estimated_finish_time = current_time_mins + estimated_remaining_mins
        if estimated_finish_time > self.shift_end_mins:
            self.violated = True
        else:
            self.violated = False
        return self.violated


class StationAgent:
    """Station/Junction Agent managing interlocking platforms as resources."""
    def __init__(self, env: simpy.Environment, station_id: str, name: str, coords: List[float], platforms: int, base_dwell_time: float):
        self.env = env
        self.station_id = station_id
        self.name = name
        self.coords = coords
        self.platforms_count = platforms
        self.base_dwell_time = base_dwell_time
        # Platform resource to govern arrival capacity
        self.resource = simpy.Resource(env, capacity=platforms)
        
        # Tracking lists
        self.occupied_platforms: List[str] = []  # Train IDs currently at platform
        self.queue: List[str] = []               # Train IDs waiting to enter station

    def request_platform(self, train_id: str):
        """Register train in queue and request platform."""
        self.queue.append(train_id)
        request = self.resource.request()
        return request

    def enter_platform(self, train_id: str):
        """Train enters platform, remove from queue, add to occupied list."""
        if train_id in self.queue:
            self.queue.remove(train_id)
        self.occupied_platforms.append(train_id)

    def release_platform(self, train_id: str, request: simpy.Request):
        """Train departs, free platform resource and update tracking."""
        if train_id in self.occupied_platforms:
            self.occupied_platforms.remove(train_id)
        self.resource.release(request)


class TrainAgent:
    """Train Agent governing motion, timetable compliance, and track reservation."""
    def __init__(
        self,
        env: simpy.Environment,
        train_id: str,
        service_type: str,
        stops: List[str],
        departure_time_mins: float,
        passenger_count: int,
        direction: str,
        engine: Any  # Reference to the SimulationEngine
    ):
        self.env = env
        self.train_id = train_id
        self.service_type = service_type
        self.stops = stops
        self.departure_time_mins = departure_time_mins
        self.passenger_count = passenger_count
        self.direction = direction
        self.original_direction = direction
        self.engine = engine

        # Operational attributes
        self.current_stop_idx = 0
        self.speed_kmh = 0.0
        self.delay_minutes = 0.0
        self.energy_consumed_kwh = 0.0
        self.status = "WAITING"  # WAITING, RUNNING, DWELLING, TERMINATED, DELAYED
        
        # State tracking for coordinate calculation
        self.from_node = stops[0]
        self.to_node = stops[0]
        self.segment_start_time = departure_time_mins
        self.segment_end_time = departure_time_mins
        self.is_dwelling = False
        self.is_waiting = True
        self.is_terminated = False
        
        # Crew agent associated with train
        self.crew = CrewAgent(f"CRW-{train_id}", train_id, shift_start_mins=max(0.0, departure_time_mins - 30.0))

    def run(self):
        """Main train traversal process loop in SimPy."""
        # 1. Wait until departure time
        if self.env.now < self.departure_time_mins:
            self.status = "WAITING"
            yield self.env.timeout(self.departure_time_mins - self.env.now)

        self.is_waiting = False
        self.status = "RUNNING"
        self.engine.log_negotiation(f"Train {self.train_id} departing from {self.stops[0]} at min {self.env.now:.1f}")

        # 2. Traverse each block segment and dwell at stations
        for i in range(len(self.stops) - 1):
            u = self.stops[i]
            v = self.stops[i+1]
            self.current_stop_idx = i

            # Update direction representation for return run under short-turn
            if len(self.stops) > 2 and self.stops[0] == self.stops[-1]:
                midpoint = len(self.stops) // 2
                if self.current_stop_idx >= midpoint:
                    self.direction = "inbound" if self.original_direction == "outbound" else "outbound"
            
            # Fetch segment details from topology
            edge_data = self.engine.topology.graph.get_edge_data(u, v)
            if not edge_data:
                continue

            travel_time = edge_data["travel_time_min"]
            distance = edge_data["distance_km"]

            # Request track resource access (Block safety lock)
            self.from_node = u
            self.to_node = v
            
            # Check if this edge is currently blocked by disruption
            is_detoured_segment = False
            if self.engine.is_track_blocked(u, v):
                if self.engine.active_recovery_strategy == "detour":
                    is_detoured_segment = True
                    self.engine.log_negotiation(f"Train {self.train_id} detouring blocked segment {u}->{v} via parallel slow line.")
                else:
                    while self.engine.is_track_blocked(u, v):
                        if self.engine.active_recovery_strategy == "detour":
                            is_detoured_segment = True
                            self.engine.log_negotiation(f"Train {self.train_id} detouring blocked segment {u}->{v} via parallel slow line.")
                            break
                        self.status = "DELAYED"
                        self.speed_kmh = 0.0
                        self.engine.log_negotiation(f"Train {self.train_id} held at {u} due to blocked track segment {u}->{v}")
                        yield self.env.timeout(1.0)  # Wait for 1 min and check again

            self.status = "RUNNING"
            current_speed = 150.0 if is_detoured_segment else 270.0
            self.speed_kmh = current_speed
            current_travel_time = travel_time * 1.8 if is_detoured_segment else travel_time

            edge_resource = None
            edge_req = None
            if not is_detoured_segment:
                # Request directional track edge block resource
                edge_resource = self.engine.get_edge_resource(u, v)
                edge_req = edge_resource.request()
                # Wait for track clearance (headway interlocking)
                yield edge_req
                self.engine.log_negotiation(f"Train {self.train_id} cleared block segment {u}->{v} at min {self.env.now:.1f}")
            else:
                self.engine.log_negotiation(f"Train {self.train_id} bypassing block segment {u}->{v} via detour track.")

            # Calculate start/end times for coordinates interpolation
            self.segment_start_time = self.env.now
            self.segment_end_time = self.env.now + current_travel_time
            
            # Model travel time along edge
            yield self.env.timeout(current_travel_time)

            # Consume energy during travel (heuristic calculation)
            # VB/Tejas have different weights, drag profiles
            mass_tons = 600.0 if self.service_type == "Vande Bharat" else 500.0 if self.service_type == "Tejas Express" else 400.0
            drag_factor = 0.0035
            efficiency = 0.85
            travel_energy = (mass_tons * 0.01 + drag_factor * current_speed) * distance / efficiency * 0.1
            if is_detoured_segment:
                travel_energy *= 1.35
            self.energy_consumed_kwh += travel_energy

            # Request platform at destination station
            station_agent: StationAgent = self.engine.stations[v]
            platform_req = station_agent.request_platform(self.train_id)
            
            # Wait until a platform is available
            wait_start = self.env.now
            yield platform_req
            wait_end = self.env.now
            
            # Release track block segment immediately after entering station
            if edge_resource and edge_req:
                edge_resource.release(edge_req)

            # Dwell at station
            station_agent.enter_platform(self.train_id)
            self.status = "DWELLING"
            self.is_dwelling = True
            self.speed_kmh = 0.0
            
            # Calculate dwell time (base dwell + platform queue delay)
            dwell_time = station_agent.base_dwell_time
            self.segment_start_time = self.env.now
            self.segment_end_time = self.env.now + dwell_time
            
            yield self.env.timeout(dwell_time)
            
            # Release platform
            station_agent.release_platform(self.train_id, platform_req)
            self.is_dwelling = False
            self.status = "RUNNING"
            
            # Accumulate delay if any
            scheduled_arrival = self.engine.get_scheduled_arrival(self.train_id, v)
            if scheduled_arrival is not None:
                self.delay_minutes = max(0.0, self.env.now - scheduled_arrival)

        # 3. Terminated at final destination
        self.status = "TERMINATED"
        self.is_terminated = True
        self.speed_kmh = 0.0
        self.from_node = self.stops[-1]
        self.to_node = self.stops[-1]
        self.engine.log_negotiation(f"Train {self.train_id} arrived at final destination {self.stops[-1]} at min {self.env.now:.1f}")

    def get_coordinates(self) -> List[float]:
        """Get the real-time interpolated [lat, lon] coordinates of the train."""
        now = self.env.now
        
        # If waiting, return departure station coords
        if self.is_waiting:
            return self.engine.topology.get_nodes()[self.stops[0]]["coords"]
            
        # If terminated, return destination coords
        if self.is_terminated:
            return self.engine.topology.get_nodes()[self.stops[-1]]["coords"]

        # If dwelling, return current station coords
        if self.is_dwelling:
            return self.engine.topology.get_nodes()[self.to_node]["coords"]

        # If running, interpolate between from_node and to_node
        coords_from = self.engine.topology.get_nodes()[self.from_node]["coords"]
        coords_to = self.engine.topology.get_nodes()[self.to_node]["coords"]
        
        total_time = self.segment_end_time - self.segment_start_time
        if total_time <= 0:
            return coords_to

        ratio = (now - self.segment_start_time) / total_time
        ratio = max(0.0, min(1.0, ratio))
        return interpolate_coords(coords_from, coords_to, ratio)
