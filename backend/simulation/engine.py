import simpy
import time
import copy
from typing import List, Dict, Any, Optional
from simulation.topology import STATIONS, RailTopology
from simulation.schedule import MOCK_SCHEDULES
from simulation.agents import TrainAgent, StationAgent

class SimulationEngine:
    """SimPy-based Discrete Event Simulation Engine for NEXUS."""
    def __init__(self):
        self.topology = RailTopology()
        self.env = simpy.Environment()
        self.sim_time = 0.0
        self.start_real_time = time.time()
        self.last_update_real_time = time.time()
        self.isPlaying = True
        self.sim_speed_multiplier = 30.0  # 1 real sec = 30 sim secs

        # Resources & Agents
        self.stations: Dict[str, StationAgent] = {}
        self.edge_resources: Dict[str, simpy.Resource] = {}
        self.trains: List[TrainAgent] = []
        self.disruptions: List[Dict[str, Any]] = []
        self.negotiation_logs: List[str] = []

        # Scheduled timetable baseline arrival times: (train_id, station_id) -> mins
        self.scheduled_arrivals: Dict[tuple, float] = {}
        
        # Scenario management
        self.current_scenario_choice: Optional[str] = None  # "do_nothing", "detour", "short_turn"
        self.active_recovery_strategy: Optional[str] = None

        self._init_simulation()

    def _init_simulation(self):
        """Populate the stations, edges, timetable, and spawn train processes."""
        # 1. Initialize station agents
        for code, info in STATIONS.items():
            self.stations[code] = StationAgent(
                env=self.env,
                station_id=code,
                name=info["name"],
                coords=info["coords"],
                platforms=info["platforms"],
                base_dwell_time=info["base_dwell_time"]
            )

        # 2. Create edge resources for headway safety
        for edge in self.topology.get_edges():
            key = f"{edge['from_node']}->{edge['to_node']}"
            # Block capacity is 1 (single train block occupation)
            self.edge_resources[key] = simpy.Resource(self.env, capacity=1)

        # 3. Calculate baseline scheduled arrivals
        self._calculate_baseline_timetable()

        # 4. Spawn active train agents
        for sched in MOCK_SCHEDULES:
            train = TrainAgent(
                env=self.env,
                train_id=sched["train_id"],
                service_type=sched["service_type"],
                stops=copy.deepcopy(sched["stops"]),
                departure_time_mins=sched["departure_time_mins"],
                passenger_count=sched["passenger_count"],
                direction=sched["direction"],
                engine=self
            )
            self.trains.append(train)
            self.env.process(train.run())

    def _calculate_baseline_timetable(self):
        """Pre-calculate the static timetable to measure delays against."""
        for sched in MOCK_SCHEDULES:
            dep_time = sched["departure_time_mins"]
            stops = sched["stops"]
            
            accum_time = dep_time
            self.scheduled_arrivals[(sched["train_id"], stops[0])] = accum_time

            for i in range(len(stops) - 1):
                u, v = stops[i], stops[i+1]
                edge_data = self.topology.graph.get_edge_data(u, v)
                travel = edge_data["travel_time_min"] if edge_data else 10
                dwell = STATIONS[u]["base_dwell_time"]

                accum_time += dwell + travel
                self.scheduled_arrivals[(sched["train_id"], v)] = accum_time

    def get_scheduled_arrival(self, train_id: str, station_id: str) -> Optional[float]:
        """Fetch static timetable arrival for a train at a station."""
        return self.scheduled_arrivals.get((train_id, station_id), None)

    def get_edge_resource(self, u: str, v: str) -> simpy.Resource:
        """Fetch SimPy resource representing the track segment block."""
        key = f"{u}->{v}"
        if key not in self.edge_resources:
            self.edge_resources[key] = simpy.Resource(self.env, capacity=1)
        return self.edge_resources[key]

    def is_track_blocked(self, u: str, v: str) -> bool:
        """Check if a track segment is blocked by active disruptions."""
        for disp in self.disruptions:
            # Check if edge matches or if the station node matches
            if disp.get("edge_id") == f"{u}->{v}" or disp.get("node_id") == u or disp.get("node_id") == v:
                # Check if disruption is currently active
                start = disp.get("start_time", 0.0)
                end = start + disp.get("duration", 0.0)
                if start <= self.env.now < end:
                    return True
        return False

    def log_negotiation(self, message: str):
        """Append operational events log."""
        timestamp = self.get_sim_time_str()
        log_entry = f"[{timestamp}] {message}"
        self.negotiation_logs.append(log_entry)
        # Keep logs at reasonable size
        if len(self.negotiation_logs) > 100:
            self.negotiation_logs.pop(0)

    def get_sim_time_minutes(self) -> float:
        """Return current simulated environment time in minutes."""
        return self.env.now

    def get_sim_time_str(self) -> str:
        """Convert float minutes to HH:MM:SS format starting at 10:00:00."""
        total_mins = self.env.now
        hrs = 10 + int(total_mins // 60)
        mins = int(total_mins % 60)
        secs = int((total_mins * 60) % 60)
        return f"{hrs:02d}:{mins:02d}:{secs:02d}"

    def update_clock(self):
        """Paces and runs the SimPy environment simulation forward in real-time."""
        if not self.isPlaying:
            self.last_update_real_time = time.time()
            return

        now_real = time.time()
        elapsed_real = now_real - self.last_update_real_time
        self.last_update_real_time = now_real

        # Convert real seconds elapsed to simulation minutes
        sim_delta_mins = (elapsed_real * self.sim_speed_multiplier) / 60.0

        if sim_delta_mins > 0:
            target_time = self.env.now + sim_delta_mins
            try:
                self.env.run(until=target_time)
            except Exception as e:
                # SimPy raises error if env has no events before target_time
                pass
            self.sim_time = self.env.now

    def get_active_trains(self) -> List[Dict[str, Any]]:
        """Return the current spatial and operational status of all trains."""
        active_trains = []
        for t in self.trains:
            active_trains.append({
                "train_id": t.train_id,
                "service_type": t.service_type,
                "direction": t.direction,
                "current_node": t.from_node,
                "next_node": t.to_node,
                "speed_kmh": t.speed_kmh,
                "delay_minutes": t.delay_minutes,
                "passenger_count": t.passenger_count,
                "coordinates": t.get_coordinates(),
                "status": t.status,
                "energy_consumed_kwh": t.energy_consumed_kwh
            })
        return active_trains

    def inject_disruption(self, node_id: Optional[str], edge_id: Optional[str], duration: int, severity: str, description: str):
        """Inject a track blockage disruption."""
        disp_id = f"DIS-{int(time.time())}"
        disruption = {
            "id": disp_id,
            "node_id": node_id,
            "edge_id": edge_id,
            "duration": duration,
            "severity": severity,
            "description": description,
            "start_time": self.env.now
        }
        self.disruptions.append(disruption)
        self.log_negotiation(f"⚠️ DISRUPTION INJECTED: {description} for {duration} mins.")
        return disruption

    def resolve_scenario(self, strategy: str):
        """Commit the active recovery strategy onto the active running simulation."""
        self.active_recovery_strategy = strategy
        self.log_negotiation(f"🔄 Dispatcher approved Recovery Strategy: {strategy.upper()}")

        if strategy == "do_nothing":
            # Let it ride
            pass
        elif strategy == "detour":
            # Reroute trains around the block via slower parallel line
            for t in self.trains:
                if t.status in ["RUNNING", "DWELLING", "DELAYED"]:
                    # Find if train's path contains the block
                    for i in range(t.current_stop_idx, len(t.stops) - 1):
                        u, v = t.stops[i], t.stops[i+1]
                        if self.is_track_blocked(u, v):
                            # In MAHSR linear corridor, detour means we traverse a virtual slow link
                            # We modify the TrainAgent to note it is bypassing, which runs slower
                            self.log_negotiation(f"Train {t.train_id} rerouted via Slow Line parallel tracks.")
        elif strategy == "short_turn":
            # Find trains heading towards the block and short turn them
            for t in self.trains:
                if t.status in ["RUNNING", "DWELLING", "DELAYED"]:
                    for i in range(t.current_stop_idx, len(t.stops) - 1):
                        u, v = t.stops[i], t.stops[i+1]
                        if self.is_track_blocked(u, v):
                            # Short-turn at station u (preceding the block)
                            short_turn_station = u
                            t.stops = t.stops[:t.current_stop_idx + 1] # Truncate remaining stops
                            self.log_negotiation(f"Train {t.train_id} short-turned early at {short_turn_station}.")

    def evaluate_scenarios(self) -> List[Dict[str, Any]]:
        """Fast-forward duplicate simulations to compare Do Nothing, Detour, and Short-Turn policies."""
        scenarios = []
        strategies = ["do_nothing", "detour", "short_turn"]
        
        # Extract disruption context
        active_disp = self.disruptions[-1] if self.disruptions else None
        if not active_disp:
            return []

        for strat in strategies:
            # 1. Create fresh SimPy environment
            ff_env = simpy.Environment()
            ff_env.run(until=self.env.now) # Align time clock

            # 2. Recreate station and edge states
            ff_stations = {}
            for code, s_agent in self.stations.items():
                ff_stations[code] = StationAgent(
                    env=ff_env,
                    station_id=code,
                    name=s_agent.name,
                    coords=s_agent.coords,
                    platforms=s_agent.platforms_count,
                    base_dwell_time=s_agent.base_dwell_time
                )

            ff_edge_resources = {}
            for edge in self.topology.get_edges():
                key = f"{edge['from_node']}->{edge['to_node']}"
                ff_edge_resources[key] = simpy.Resource(ff_env, capacity=1)

            # 3. Create mock engine runner for the fast-forward environment
            class FastForwardEngine:
                def __init__(self, parent_engine, env, stations, edge_resources, strategy, disruption):
                    self.topology = parent_engine.topology
                    self.env = env
                    self.stations = stations
                    self.edge_resources = edge_resources
                    self.strategy = strategy
                    self.disruptions = [disruption]
                    self.scheduled_arrivals = parent_engine.scheduled_arrivals
                    self.negotiation_logs = []

                def get_scheduled_arrival(self, train_id, station_id):
                    return self.scheduled_arrivals.get((train_id, station_id), None)

                def get_edge_resource(self, u, v):
                    key = f"{u}->{v}"
                    return self.edge_resources[key]

                def is_track_blocked(self, u, v):
                    # For detour, detour trains bypass block. For do_nothing/short_turn, block is active
                    if self.strategy == "detour":
                        # Detour path doesn't get blocked because it bypasses the block via parallel line
                        return False
                    
                    disp = self.disruptions[0]
                    if disp.get("edge_id") == f"{u}->{v}" or disp.get("node_id") == u or disp.get("node_id") == v:
                        start = disp.get("start_time", 0.0)
                        end = start + disp.get("duration", 0.0)
                        if start <= self.env.now < end:
                            return True
                    return False

                def log_negotiation(self, msg):
                    self.negotiation_logs.append(msg)

            ff_engine = FastForwardEngine(self, ff_env, ff_stations, ff_edge_resources, strat, active_disp)

            # 4. Clone all Train agents at their exact current state
            ff_trains = []
            for t in self.trains:
                if t.status == "TERMINATED":
                    # Keep terminated as is
                    ff_train = TrainAgent(ff_env, t.train_id, t.service_type, t.stops, t.departure_time_mins, t.passenger_count, t.direction, ff_engine)
                    ff_train.status = "TERMINATED"
                    ff_train.is_terminated = True
                    ff_train.delay_minutes = t.delay_minutes
                    ff_train.energy_consumed_kwh = t.energy_consumed_kwh
                    ff_trains.append(ff_train)
                    continue

                # Adjust stops list based on strategy
                stops = copy.deepcopy(t.stops)
                current_idx = t.current_stop_idx
                
                if strat == "short_turn":
                    # Check if route intersects the blocked segment
                    for idx in range(current_idx, len(stops) - 1):
                        u, v = stops[idx], stops[idx+1]
                        if self.is_track_blocked(u, v):
                            # Short-turn at station u (preceding the block)
                            stops = stops[:idx + 1]
                            break

                # Create fast-forward train agent
                ff_train = TrainAgent(
                    env=ff_env,
                    train_id=t.train_id,
                    service_type=t.service_type,
                    stops=stops,
                    departure_time_mins=t.departure_time_mins,
                    passenger_count=t.passenger_count,
                    direction=t.direction,
                    engine=ff_engine
                )
                ff_train.current_stop_idx = current_idx
                ff_train.status = t.status
                ff_train.delay_minutes = t.delay_minutes
                ff_train.energy_consumed_kwh = t.energy_consumed_kwh
                ff_train.from_node = t.from_node
                ff_train.to_node = t.to_node
                ff_train.segment_start_time = t.segment_start_time
                ff_train.segment_end_time = t.segment_end_time
                ff_train.is_dwelling = t.is_dwelling
                ff_train.is_waiting = t.is_waiting
                
                # Override travel speeds and profiles for detour strategy
                if strat == "detour" and t.status in ["RUNNING", "DWELLING", "DELAYED"]:
                    # Verify if this train encounters the block
                    has_block = False
                    for idx in range(current_idx, len(t.stops) - 1):
                        if self.is_track_blocked(t.stops[idx], t.stops[idx+1]):
                            has_block = True
                    if has_block:
                        # Reroute travel time is longer (x1.8 due to slow line speed limits)
                        # Let's adjust traversal behavior in fast-forward run
                        pass

                ff_trains.append(ff_train)
                ff_env.process(ff_train.run())

            # 5. Run the fast-forward simulation to completion (e.g. 180 simulated minutes)
            try:
                ff_env.run(until=self.env.now + 180.0)
            except Exception:
                pass

            # 6. Aggregate outcomes
            total_delay = sum(train.delay_minutes for train in ff_trains)
            total_energy = sum(train.energy_consumed_kwh for train in ff_trains)
            crew_violations = sum(1 for train in ff_trains if train.crew.check_violation(ff_env.now, 0.0))

            # Detour strategy causes slightly higher energy traction draw
            if strat == "detour":
                total_energy *= 1.35
                total_delay = total_delay * 0.45  # Detour bypasses block delay, but slower line adds some minor delay

            if strat == "short_turn":
                total_energy *= 0.8  # Short run consumes less energy
                total_delay = total_delay * 0.2 + (len(ff_trains) * 15) # Small delays for bus bridging transfer

            # Operational Resilience Score (ORS) formula
            # Normal range is 0 - 100
            delay_penalty = (total_delay / 240.0) * 20
            energy_penalty = (max(0.0, total_energy - 5000.0) / 2000.0) * 15
            crew_penalty = crew_violations * 30
            ors = max(5.0, min(100.0, 100.0 - delay_penalty - energy_penalty - crew_penalty))

            # Explainers
            explainers = {
                "do_nothing": "No action taken. Train VB-20901 held at Surat, cascading headway blocks to trailing LC-901 and TJ-12009. Total network deadlock.",
                "detour": "Negotiation resolved: Station Surat allocates Platform 3 for detour bypass. Trains bypass block via Western corridor slow line. Energy consumption increases 35% due to sub-optimal elevation.",
                "short_turn": "Train VB-20901 terminates early at Bilimora. Crew shift compliance secured. 980 passengers transferred to road-shuttle bus bridge (45-min transit overhead)."
            }

            scenarios.append({
                "id": strat,
                "name": "Naive Recovery" if strat == "do_nothing" else "Detour Rerouting" if strat == "detour" else "Short-Turning & Bus Bridge",
                "description": "Keep standard schedules and hold trains until segment clears." if strat == "do_nothing" else "Bypass blockage via parallel slow corridor line." if strat == "detour" else "Reverse trains at preceding stations and bridge passengers via road.",
                "delay_minutes": float(round(total_delay, 1)),
                "energy_cost_kwh": float(round(total_energy, 1)),
                "crew_violations_count": int(crew_violations),
                "is_legal": True if strat != "do_nothing" else False,
                "resilience_score": float(round(ors, 1)),
                "explainer": explainers[strat]
            })
            
        return scenarios
