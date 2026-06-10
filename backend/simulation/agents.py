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
        self.waiting_trains: List[tuple] = []    # List of (TrainAgent, env.event)

    def request_platform(self, train: Any):
        """Register train in queue and request platform, resolving via VCG auction if constrained."""
        train_id = train if isinstance(train, str) else train.train_id
        
        # Check if platform is free and queue is empty
        if len(self.occupied_platforms) < self.platforms_count and not self.waiting_trains:
            self.occupied_platforms.append(train_id)
            event = self.env.event()
            event.succeed()
            return event

        # Otherwise queue up and participate in next VCG auction
        event = self.env.event()
        self.queue.append(train_id)
        
        train_agent = train
        if isinstance(train, str):
            # Try to lookup in engine trains if possible
            train_agent = None
            if hasattr(self.env, "trains"):
                train_agent = next((t for t in self.env.trains if t.train_id == train), None)
            if not train_agent:
                # Mock a train agent for backward compatibility in tests
                class MockTrain:
                    def __init__(self, tid):
                        self.train_id = tid
                        self.priority_tokens = 100.0
                        self.bids_paid = 0.0
                        self.service_type = "Local"
                        self.passenger_count = 500
                        self.delay_minutes = 0.0
                    def calculate_platform_bid(self):
                        return 10.0
                train_agent = MockTrain(train)
                
        self.waiting_trains.append((train_agent, event))
        return event

    def enter_platform(self, train: Any):
        """Train enters platform, remove from queue, add to occupied list."""
        train_id = train if isinstance(train, str) else train.train_id
        if train_id in self.queue:
            self.queue.remove(train_id)
        if train_id not in self.occupied_platforms:
            self.occupied_platforms.append(train_id)

    def release_platform(self, train: Any, request: Any):
        """Train departs, free platform resource and run VCG auction to dispatch next train."""
        train_id = train if isinstance(train, str) else train.train_id
        if train_id in self.occupied_platforms:
            self.occupied_platforms.remove(train_id)
            
        # Run VCG auction to allocate the freed platform
        if self.waiting_trains:
            bids = []
            for t, ev in self.waiting_trains:
                if isinstance(t, str):
                    bid_val = 10.0
                else:
                    bid_val = t.calculate_platform_bid()
                bids.append((t, ev, bid_val))
                
            # Sort descending by bid value
            bids.sort(key=lambda x: x[2], reverse=True)
            
            # Winner is the highest bidder
            winner_t, winner_event, winning_bid = bids[0]
            
            # VCG payment is second-price (opportunity cost) or 0 if only 1 bidder
            payment = 0.0
            if len(bids) > 1:
                payment = bids[1][2]
                
            # Deduct tokens from winner
            if not isinstance(winner_t, str):
                winner_t.priority_tokens = max(0.0, winner_t.priority_tokens - payment)
                winner_t.bids_paid += payment
                
                # Log auction result to the dispatcher log
                if hasattr(winner_t, "engine") and winner_t.engine:
                    bids_str = ", ".join([f"{x[0] if isinstance(x[0], str) else x[0].train_id}:{x[2]:.1f}" for x in bids])
                    winner_t.engine.log_negotiation(
                        f"🎫 VCG AUCTION at {self.name}: Train {winner_t.train_id} wins platform slot "
                        f"with bid {winning_bid:.1f} tokens. Paid second-price: {payment:.1f} tokens. (Bids: [{bids_str}])"
                    )
            
            # Remove winner from waiting lists
            self.waiting_trains = [item for item in self.waiting_trains if item[1] != winner_event]
            winner_id = winner_t if isinstance(winner_t, str) else winner_t.train_id
            if winner_id in self.queue:
                self.queue.remove(winner_id)
                
            self.occupied_platforms.append(winner_id)
            winner_event.succeed()


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
        
        # Game-theory token bidding attributes
        self.priority_tokens = 100.0
        self.bids_paid = 0.0
        
        # State tracking for coordinate calculation
        self.from_node = stops[0]
        self.to_node = stops[0]
        self.segment_start_time = departure_time_mins
        self.segment_end_time = departure_time_mins
        self.is_dwelling = False
        self.is_waiting = True
        self.is_terminated = False
        self.traveled_distance_on_segment = 0.0
        
        # Advanced physics and telemetry attributes
        self.voltage = 25000.0
        self.telemetry_packet_lost = False
        self.short_turn_depot = None
        
        # Crew agent associated with train
        self.crew = CrewAgent(f"CRW-{train_id}", train_id, shift_start_mins=max(0.0, departure_time_mins - 30.0))

    def calculate_platform_bid(self) -> float:
        """Calculate the virtual token bid for the platform based on priority, delay and passenger count."""
        priority_weights = {
            "Vande Bharat": 1.5,
            "Tejas Express": 1.2,
            "Local": 0.8
        }
        multiplier = priority_weights.get(self.service_type, 1.0)
        # Bid scaled by passengers and delay, capped by remaining tokens
        base_bid = (self.passenger_count / 100.0) * multiplier * (1.0 + self.delay_minutes)
        return min(self.priority_tokens, base_bid)

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

            # If departing from a short-turn depot, lock the crossover for 2 minutes
            if getattr(self, "short_turn_depot", None) == u:
                self.engine.crossover_locks[u] = self.env.now + 2.0
                self.engine.log_negotiation(f"🔒 CROSSOVER LOCK: Train {self.train_id} locking crossover at {u} for 2.0 minutes for reversing.")
                self.short_turn_depot = None

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
            is_detoured_segment = edge_data.get("is_slow", False)
            if self.engine.is_track_blocked(u, self.stops[self.current_stop_idx + 1]):
                while self.engine.is_track_blocked(u, self.stops[self.current_stop_idx + 1]):
                    self.status = "DELAYED"
                    self.speed_kmh = 0.0
                    self.engine.log_negotiation(f"Train {self.train_id} held at {u} due to blocked track segment {u}->{self.stops[self.current_stop_idx + 1]}")
                    
                    # Accumulate delay and replenish tokens
                    scheduled_arrival = self.engine.get_scheduled_arrival(self.train_id, self.stops[self.current_stop_idx + 1])
                    if scheduled_arrival is not None:
                        self.delay_minutes = max(0.0, self.env.now - scheduled_arrival)
                    self.priority_tokens += 10 * (0.05 * self.delay_minutes)  # 1.0 sim minute wait = 10 ticks worth
                    
                    yield self.env.timeout(1.0)  # Wait for 1 min and check again
                
                # Update segment data in case stops were dynamically changed during wait
                v = self.stops[self.current_stop_idx + 1]
                edge_data = self.engine.topology.graph.get_edge_data(u, v)
                if not edge_data:
                    continue
                travel_time = edge_data["travel_time_min"]
                distance = edge_data["distance_km"]
                is_detoured_segment = edge_data.get("is_slow", False)
                edge_key = f"{u}->{v}"

            self.status = "RUNNING"
            base_speed = 150.0 if is_detoured_segment else 270.0
            self.speed_kmh = base_speed

            self.traveled_distance_on_segment = 0.0
            self.segment_start_time = self.env.now
            self.segment_end_time = self.env.now + (travel_time * 1.8 if is_detoured_segment else travel_time)
            
            # Step size in minutes (e.g. 0.1 minutes)
            dt = 0.1
            last_log_state = None
            
            mass_tons = 600.0 if self.service_type == "Vande Bharat" else 500.0 if self.service_type == "Tejas Express" else 400.0
            drag_factor = 0.0035
            efficiency = 0.85

            edge_key = f"{u}->{v}"

            while self.traveled_distance_on_segment < distance:
                # 1. Check substation breaker status and power limits
                max_speed_limit = base_speed
                trip_time = self.engine.substation_tripped.get(edge_key, None)
                if trip_time is not None:
                    if self.env.now - trip_time >= 1.5:
                        self.engine.substation_tripped[edge_key] = None
                        self.engine.log_negotiation(f"⚡ Substation breaker on {u}->{v} reset. Catenary power restored to full 25kV.")
                        max_speed_limit = base_speed
                    else:
                        max_speed_limit = 50.0
                else:
                    # Calculate total current draw on the edge
                    total_amps = self.engine.get_edge_current_draw(u, v)
                    if total_amps > self.engine.substation_limit:
                        self.engine.substation_tripped[edge_key] = self.env.now
                        self.engine.log_negotiation(
                            f"⚠️ SUBSTATION TRIP: Catenary load on {u}->{v} exceeded capacity "
                            f"({total_amps:.1f}A > {self.engine.substation_limit}A). Circuit breaker tripped! "
                            f"Restricting speeds to 50 km/h."
                        )
                        max_speed_limit = 50.0

                # 1a. Electrical Voltage Degradation
                current_draw_amps = (mass_tons * 0.01 + 0.0005 * (self.speed_kmh ** 2)) * 3.5
                line_resistance_ohms = 0.05 * self.traveled_distance_on_segment
                self.voltage = max(0.0, 25000.0 - current_draw_amps * line_resistance_ohms)
                if self.voltage < 22000.0:
                    voltage_scale = self.voltage / 25000.0
                    max_speed_limit *= voltage_scale

                # 1b. Telemetry Packet Loss Jitter (2% chance per tick)
                import random
                self.telemetry_packet_lost = (random.random() < 0.02)
                if self.telemetry_packet_lost:
                    max_speed_limit = min(max_speed_limit, 50.0)

                # 1c. Token Starvation Prevention Tax
                scheduled_next_arrival = self.engine.get_scheduled_arrival(self.train_id, v)
                if scheduled_next_arrival is not None:
                    self.delay_minutes = max(0.0, self.env.now - scheduled_next_arrival)
                self.priority_tokens += 0.05 * self.delay_minutes

                # 2. Find leading train and distance on the same segment
                leading_dist = float('inf')
                leading_train_id = None
                
                # Check for active track crossover lock at destination station v
                if self.engine.crossover_locks.get(v, 0.0) > self.env.now:
                    dist = distance - self.traveled_distance_on_segment
                    if dist < leading_dist:
                        leading_dist = dist
                        leading_train_id = f"CrossoverLock@{v}"

                for other in self.engine.trains:
                    if other.train_id == self.train_id:
                        continue
                    if other.is_terminated or other.is_waiting:
                        continue
                    
                    # Case A: Leading train is running on the same segment u -> v ahead of us
                    if other.from_node == u and other.to_node == v and not other.is_dwelling:
                        if hasattr(other, "traveled_distance_on_segment"):
                            other_dist = other.traveled_distance_on_segment
                            if other_dist > self.traveled_distance_on_segment:
                                dist = other_dist - self.traveled_distance_on_segment
                                if dist < leading_dist:
                                    leading_dist = dist
                                    leading_train_id = other.train_id
                                    
                    # Case B: Leading train is dwelling at the destination station v
                    elif other.to_node == v and other.is_dwelling:
                        dist = distance - self.traveled_distance_on_segment
                        if dist < leading_dist:
                            leading_dist = dist
                            leading_train_id = other.train_id

                # 3. Determine target speed based on ATC Braking Curve
                if leading_dist >= 5.0:
                    target_speed = base_speed
                    state = "NORMAL"
                elif leading_dist >= 1.0:
                    # Linear braking curve down to 30 km/h
                    target_speed = 30.0 + (base_speed - 30.0) * ((leading_dist - 1.0) / 4.0)
                    state = "THROTTLED"
                elif leading_dist >= 0.2:
                    target_speed = 15.0
                    state = "CRAWLING"
                else:
                    target_speed = 0.0
                    state = "STOPPED"

                # Apply speed restriction based on catenary power, voltage degradation, or telemetry loss
                if max_speed_limit < target_speed:
                    target_speed = max_speed_limit
                    if self.telemetry_packet_lost:
                        state = "TELEMETRY_LOST"
                    elif self.voltage < 22000.0:
                        state = "VOLTAGE_DEGRADED"
                    else:
                        state = "SUBSTATION_THROTTLED"

                self.speed_kmh = target_speed
                
                # Log state change to avoid spam
                if state != last_log_state:
                    if state == "THROTTLED":
                        self.engine.log_negotiation(f"Train {self.train_id} speed throttled to {self.speed_kmh:.1f} km/h due to spacing headway ({leading_dist:.2f} km) behind {leading_train_id}")
                    elif state == "CRAWLING":
                        self.engine.log_negotiation(f"Train {self.train_id} entering ATC crawl (15 km/h) due to close headway spacing behind {leading_train_id}")
                    elif state == "STOPPED":
                        self.engine.log_negotiation(f"Train {self.train_id} stopped to avoid collision behind {leading_train_id}")
                    elif state == "SUBSTATION_THROTTLED":
                        self.engine.log_negotiation(f"Train {self.train_id} throttled to {self.speed_kmh:.1f} km/h due to catenary substation trip on segment {u}->{v}")
                    elif state == "TELEMETRY_LOST":
                        self.engine.log_negotiation(f"📡 TELEMETRY LOSS: Train {self.train_id} lost communication packet. Safe crawl speed of 50 km/h active.")
                    elif state == "VOLTAGE_DEGRADED":
                        self.engine.log_negotiation(f"⚡ VOLTAGE DEGRADATION: Train {self.train_id} catenary voltage dropped to {self.voltage:.1f}V. Speed scaled to {self.speed_kmh:.1f} km/h.")
                    last_log_state = state

                # 3. Compute distance covered in this time step (in hours)
                dt_hours = dt / 60.0
                distance_step = self.speed_kmh * dt_hours
                
                # Consume energy for this step
                step_energy = (mass_tons * 0.01 + drag_factor * self.speed_kmh) * distance_step / efficiency * 0.1
                if is_detoured_segment:
                    step_energy *= 1.35
                self.energy_consumed_kwh += step_energy

                # Check if we reach the destination in this step
                if self.traveled_distance_on_segment + distance_step >= distance:
                    remaining_dist = distance - self.traveled_distance_on_segment
                    if self.speed_kmh > 0:
                        actual_dt = (remaining_dist / self.speed_kmh) * 60.0
                    else:
                        actual_dt = dt
                    self.traveled_distance_on_segment = distance
                    yield self.env.timeout(actual_dt)
                    break
                else:
                    self.traveled_distance_on_segment += distance_step
                    # Dynamically update segment_end_time so coordinate interpolation remains accurate
                    if self.speed_kmh > 0:
                        self.segment_end_time = self.env.now + ((distance - self.traveled_distance_on_segment) / self.speed_kmh) * 60.0
                    else:
                        self.segment_end_time = self.env.now + 999.0
                    yield self.env.timeout(dt)

            # Request platform at destination station
            station_agent: StationAgent = self.engine.stations[v]
            platform_req = station_agent.request_platform(self)
            
            # Wait until a platform is available
            yield platform_req

            # Dwell at station
            station_agent.enter_platform(self)
            self.status = "DWELLING"
            self.is_dwelling = True
            self.speed_kmh = 0.0
            
            # Calculate dwell time (base dwell + platform queue delay)
            if v.endswith("_SLOW"):
                dwell_time = 0.0
            else:
                dwell_time = station_agent.base_dwell_time
                if hasattr(self.engine, "strategy"):
                    import random
                    dwell_time += random.uniform(-0.5, 2.5)
                    dwell_time = max(0.5, dwell_time)

            self.segment_start_time = self.env.now
            self.segment_end_time = self.env.now + dwell_time
            
            yield self.env.timeout(dwell_time)
            
            # Release platform
            station_agent.release_platform(self, platform_req)
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
        
        edge_data = self.engine.topology.graph.get_edge_data(self.from_node, self.to_node)
        if edge_data and "distance_km" in edge_data:
            distance = edge_data["distance_km"]
            if distance > 0:
                ratio = self.traveled_distance_on_segment / distance
                ratio = max(0.0, min(1.0, ratio))
                return interpolate_coords(coords_from, coords_to, ratio)

        total_time = self.segment_end_time - self.segment_start_time
        if total_time <= 0:
            return coords_to

        ratio = (now - self.segment_start_time) / total_time
        ratio = max(0.0, min(1.0, ratio))
        return interpolate_coords(coords_from, coords_to, ratio)
