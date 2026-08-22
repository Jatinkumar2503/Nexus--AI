import sys
import os

# Add parent directory to path so python can import simulation package
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from simulation.engine import SimulationEngine, get_non_linear_delay
from simulation.agents import CrewAgent, TrainAgent

def test_simulation_initialization():
    print("Testing Simulation Initialization...")
    engine = SimulationEngine()
    assert len(engine.stations) == 24, f"Expected 24 stations (12 main + 12 slow), got {len(engine.stations)}"
    assert len(engine.trains) == 8, f"Expected 8 trains, got {len(engine.trains)}"
    assert len(engine.scheduled_arrivals) > 0, "Scheduled baseline timetable is empty!"
    print("OK: Simulation Initialization passed.\n")

def test_detour_routing_mechanics():
    print("Testing Detour Routing Mechanics...")
    engine = SimulationEngine()
    
    # Inject disruption on SUR->BHA segment
    engine.inject_disruption(
        node_id=None,
        edge_id="SUR->BHA",
        duration=120,
        severity="HIGH",
        description="Signal cables theft"
    )
    
    # Resolve using detour strategy
    engine.resolve_scenario("detour")
    assert engine.active_recovery_strategy == "detour"
    
    # Find a train that traverses SUR->BHA, e.g. LC-901
    target_train = next((t for t in engine.trains if "SUR" in t.stops and "BHA" in t.stops), None)
    assert target_train is not None, "Could not find a train traversing SUR->BHA"
    
    # Run simulation forward until LC-901 enters the SUR->BHA segment
    max_time = 200.0
    detour_detected = False
    while engine.env.now < max_time:
        engine.env.run(until=engine.env.now + 2.0)
        # Check active status of LC-901
        for t in engine.trains:
            if t.train_id == "LC-901" and t.from_node == "SUR_SLOW" and t.to_node == "BHA_SLOW" and t.status == "RUNNING":
                detour_detected = True
                assert t.speed_kmh == 150.0, f"Expected detour speed of 150 km/h, got {t.speed_kmh}"
                break
        if detour_detected:
            break
            
    assert detour_detected, "LC-901 never reached SUR_SLOW->BHA_SLOW detour segment during the test window!"
    print("OK: Detour Routing Mechanics passed.\n")

def test_short_turn_mechanics():
    print("Testing Short-Turn Routing Mechanics...")
    engine = SimulationEngine()
    
    # Run the simulation for 20 minutes first so trains are active and in RUNNING status
    engine.env.run(until=20.0)
    
    # Inject disruption on SUR->BHA segment
    engine.inject_disruption(
        node_id=None,
        edge_id="SUR->BHA",
        duration=120,
        severity="HIGH",
        description="Track derailment at Surat"
    )
    
    # Find a train heading towards the block, e.g. LC-901
    target_train = next((t for t in engine.trains if t.train_id == "LC-901"), None)
    assert target_train is not None
    assert target_train.status in ["RUNNING", "DWELLING", "DELAYED"]
    original_stops = list(target_train.stops)
    
    # Resolve using short-turn strategy
    engine.resolve_scenario("short_turn")
    assert engine.active_recovery_strategy == "short_turn"
    
    # Verify stops are updated to return early
    new_stops = target_train.stops
    assert len(new_stops) > 0
    assert "BHA" not in new_stops, "Block station should be removed from stops under short-turn!"
    assert new_stops[-1] == original_stops[0], "Train should return to its origin station!"
    print(f"Short-turn stops: {' -> '.join(new_stops)}")
    print("OK: Short-Turn Routing Mechanics passed.\n")

def test_crew_roster_violation():
    print("Testing Crew Roster Violations...")
    # Standard crew agent with max shift duration 480 mins (8 hours)
    crew = CrewAgent("CRW-TEST", "TEST-TRAIN", shift_start_mins=10.0)
    
    # Current time = 100.0, remaining = 300.0 => 400.0 < 490.0 (shift end) -> No violation
    assert not crew.check_violation(current_time_mins=100.0, estimated_remaining_mins=300.0)
    
    # Current time = 100.0, remaining = 400.0 => 500.0 > 490.0 -> Violation!
    assert crew.check_violation(current_time_mins=100.0, estimated_remaining_mins=400.0)
    
    # Train agent exposes crew violation check
    engine = SimulationEngine()
    train = engine.trains[0]
    # Set high remaining stops to trigger violation
    train.stops = ["SAB"] * 40
    active_trains = engine.get_active_trains()
    # Find active train state for the first train
    train_state = next(t for t in active_trains if t["train_id"] == train.train_id)
    assert train_state["crew_violated"] is True, "Crew violation flag not set on train state!"
    print("OK: Crew Roster Violations passed.\n")

def test_monte_carlo_scenarios():
    print("Testing Monte Carlo Scenario Evaluation...")
    engine = SimulationEngine()
    engine.inject_disruption(
        node_id="SUR",
        edge_id=None,
        duration=90,
        severity="HIGH",
        description="Signal failures"
    )
    
    scenarios = engine.evaluate_scenarios()
    assert len(scenarios) == 3, f"Expected 3 recovery scenarios, got {len(scenarios)}"
    
    for s in scenarios:
        assert s["id"] in ["do_nothing", "detour", "short_turn"]
        assert s["resilience_score"] > 0
        assert s["delay_minutes"] >= 0
        assert s["energy_cost_kwh"] >= 0
        assert "explainer" in s
        assert len(s["explainer"]) > 0
        assert "is_pareto_optimal" in s
        assert isinstance(s["is_pareto_optimal"], bool)
        print(f"Scenario: {s['name']} | ORS: {s['resilience_score']} | Pareto: {s['is_pareto_optimal']} | Explainer: {s['explainer']}")
        
    print("OK: Monte Carlo Scenario Evaluation passed.\n")

def test_dynamic_spacing_headways():
    print("Testing Dynamic Spacing Headways (ATC Braking Curves)...")
    from simulation.schedule import MOCK_SCHEDULES
    
    # Temporarily set departure times of the first two trains to 0.0
    orig_dep_1 = MOCK_SCHEDULES[0]["departure_time_mins"]
    orig_dep_2 = MOCK_SCHEDULES[1]["departure_time_mins"]
    MOCK_SCHEDULES[0]["departure_time_mins"] = 0
    MOCK_SCHEDULES[1]["departure_time_mins"] = 0
    
    try:
        engine = SimulationEngine()
        
        t1 = next(t for t in engine.trains if t.train_id == "VB-20901")
        t2 = next(t for t in engine.trains if t.train_id == "TJ-12009")
        
        # Run a tiny bit to initialize the segment loop inside SimPy
        engine.env.run(until=0.01)
        
        # Override positions now that they have passed initialization
        t1.traveled_distance_on_segment = 4.0
        t2.traveled_distance_on_segment = 1.0
        
        # Advance simulation past the first event wakeup (0.1 mins) to 0.11 mins
        engine.env.run(until=0.11)
        
        # Headway is 4.45 - 1.0 = 3.45 km.
        # Target speed for Tejas (base speed 270 km/h) with 3.45 km headway is:
        # 30 + (270 - 30) * ((3.45 - 1.0) / 4.0) = 30 + 240 * 0.6125 = 177.0 km/h.
        assert 170.0 < t2.speed_kmh < 180.0, f"Expected speed around 177 km/h, got {t2.speed_kmh}"
        print(f"OK: Spacing headway throttled train speed to {t2.speed_kmh:.1f} km/h (base was 270 km/h).")
    finally:
        # Restore original schedules
        MOCK_SCHEDULES[0]["departure_time_mins"] = orig_dep_1
        MOCK_SCHEDULES[1]["departure_time_mins"] = orig_dep_2
        
    print("OK: Dynamic Spacing Headways passed.\n")

def test_axle_telemetry_ingest():
    print("Testing Sub-Second Axle Telemetry Ingest...")
    engine = SimulationEngine()
    
    # Ingest a mock telemetry event
    msg = engine.ingest_telemetry(
        axle_counter_id="AX-SUR-BHA-ENTRY",
        train_id="VB-20901",
        timestamp=1420000000.123,
        axle_count=64,
        event_type="entry"
    )
    
    # Verify log format and containment
    assert "AX-SUR-BHA-ENTRY" in msg
    assert "VB-20901" in msg
    assert "64 axles confirmed" in msg
    assert any(msg in log for log in engine.negotiation_logs)
    print(f"OK: Telemetry parsed and logged successfully: {msg}")
    print("OK: Sub-Second Axle Telemetry Ingest passed.\n")

def test_non_linear_delay_cost():
    print("Testing Non-Linear Delay Cost Curve...")
    
    # 10 mins (<= 15 mins threshold): Should remain linear
    assert get_non_linear_delay(10.0) == 10.0, "Expected linear cost for <= 15 minutes delay"
    
    # 15 mins (exact threshold boundary)
    assert get_non_linear_delay(15.0) == 15.0, "Expected exact match at threshold boundary"
    
    # 25 mins (> 15 mins threshold): 15.0 + 10.0 + 0.1 * 100 = 35.0
    cost_25 = get_non_linear_delay(25.0)
    assert cost_25 == 35.0, f"Expected exponentially scaled cost of 35.0, got {cost_25}"
    
    print(f"OK: Non-linear delay cost verified: 10m -> {get_non_linear_delay(10.0)}m, 25m -> {cost_25}m")
    print("OK: Non-Linear Delay Cost Curve passed.\n")

def test_catenary_substation_solver():
    print("Testing Catenary Substation Power Flow Solver...")
    engine = SimulationEngine()
    
    t1 = next(t for t in engine.trains if t.train_id == "VB-20901")
    t2 = next(t for t in engine.trains if t.train_id == "TJ-12009")
    
    t1.from_node = "MUM"
    t1.to_node = "TNA"
    t1.status = "RUNNING"
    t1.speed_kmh = 270.0
    
    t2.from_node = "MUM"
    t2.to_node = "TNA"
    t2.status = "RUNNING"
    t2.speed_kmh = 270.0
    
    # Check total current draw on MUM->TNA
    total_amps = engine.get_edge_current_draw("MUM", "TNA")
    assert 290.0 < total_amps < 296.0, f"Expected draw around 293 Amps, got {total_amps}"
    print(f"OK: Verified combined current draw of {total_amps:.1f}A on segment MUM->TNA.")
    
    # Check trip logic under high load
    from simulation.schedule import MOCK_SCHEDULES
    orig_dep_1 = MOCK_SCHEDULES[0]["departure_time_mins"]
    orig_dep_2 = MOCK_SCHEDULES[1]["departure_time_mins"]
    MOCK_SCHEDULES[0]["departure_time_mins"] = 0
    MOCK_SCHEDULES[1]["departure_time_mins"] = 0
    
    try:
        engine_trip = SimulationEngine()
        engine_trip.substation_limit = 200.0
        
        t1_trip = next(t for t in engine_trip.trains if t.train_id == "VB-20901")
        t2_trip = next(t for t in engine_trip.trains if t.train_id == "TJ-12009")
        
        # Override positions past initialization to keep them on MUM->TNA
        engine_trip.env.run(until=0.01)
        t1_trip.traveled_distance_on_segment = 8.0
        t2_trip.traveled_distance_on_segment = 1.0
        
        # Override speeds to draw high current
        t1_trip.speed_kmh = 270.0
        t2_trip.speed_kmh = 270.0
        
        # Run environment slightly to trigger next step and evaluate power flow
        engine_trip.env.run(until=0.11)
        
        # Substation trip should be active
        trip_active = engine_trip.substation_tripped.get("MUM->TNA") is not None
        assert trip_active, "Substation breaker should have tripped!"
        # Speed of trailing train t2 should be restricted to 50 km/h due to substation throttling
        assert t2_trip.speed_kmh == 50.0, f"Expected throttled speed 50 km/h, got {t2_trip.speed_kmh}"
        print(f"OK: Substation limiter successfully tripped and throttled trailing train speed to {t2_trip.speed_kmh:.1f} km/h.")
        
    finally:
        MOCK_SCHEDULES[0]["departure_time_mins"] = orig_dep_1
        MOCK_SCHEDULES[1]["departure_time_mins"] = orig_dep_2
        
    print("OK: Catenary Substation Power Flow Solver passed.\n")

def test_crew_depot_allocation_constraints():
    print("Testing Crew-Depot Allocation Constraints...")
    engine = SimulationEngine()
    
    # Run the simulation for 20 minutes first so trains are active
    engine.env.run(until=20.0)
    
    # Inject disruption on BIL->SUR segment
    engine.inject_disruption(
        node_id=None,
        edge_id="BIL->SUR",
        duration=120,
        severity="HIGH",
        description="Overhead catenary snapped between Bilimora and Surat"
    )
    
    # Find a train heading towards the block, e.g. LC-901
    target_train = next((t for t in engine.trains if t.train_id == "LC-901"), None)
    assert target_train is not None
    assert target_train.status in ["RUNNING", "DWELLING", "DELAYED"]
    
    # Resolve using short-turn strategy
    engine.resolve_scenario("short_turn")
    assert engine.active_recovery_strategy == "short_turn"
    
    # Verify stops are updated to return early at VAP (crew depot) instead of BIL (non-depot)
    new_stops = target_train.stops
    assert len(new_stops) > 0
    # "BIL" is the station before "SUR", but not a depot. "VAP" is the closest depot before "BIL".
    assert "SUR" not in new_stops
    assert "BIL" not in new_stops, "Train should have short-turned at VAP (depot) instead of BIL (non-depot)"
    assert "VAP" in new_stops, "Train should short-turn at VAP"
    # The last stop should be origin "MUM"
    assert new_stops[-1] == "MUM", "Train should return to MUM"
    print(f"Verified crew-depot short-turn stops: {' -> '.join(new_stops)}")
    print("OK: Crew-Depot Allocation Constraints passed.\n")

def test_game_theory_token_bidding():
    print("Testing Game-Theory Token Bidding (VCG Platform Auction)...")
    engine = SimulationEngine()
    
    # Let's set up a station with 1 platform capacity, e.g. SUR (Surat)
    sur_station = engine.stations["SUR"]
    sur_station.platforms_count = 1
    
    # Clear occupied platforms and waiting trains
    sur_station.occupied_platforms = []
    sur_station.waiting_trains = []
    sur_station.queue = []
    
    # We will create three mock or actual train agents to request platforms
    # Train 1 (high priority Vande Bharat, e.g., delay = 10 mins)
    t1 = next(t for t in engine.trains if t.train_id == "VB-20901")
    t1.delay_minutes = 10.0
    t1.priority_tokens = 100.0
    t1.bids_paid = 0.0
    
    # Train 2 (lower priority Local, e.g. delay = 5 mins)
    t2 = next(t for t in engine.trains if t.train_id == "LC-901")
    t2.delay_minutes = 5.0
    t2.priority_tokens = 100.0
    t2.bids_paid = 0.0
    
    # 1. Occupy the platform with a mock train first so it's fully occupied
    sur_station.occupied_platforms.append("MOCK_OCCUPANT")
    
    # 2. Both trains request the platform and must queue
    req1 = sur_station.request_platform(t1)
    req2 = sur_station.request_platform(t2)
    
    assert len(sur_station.waiting_trains) == 2
    assert t1.train_id in sur_station.queue
    assert t2.train_id in sur_station.queue
    
    # Check bids:
    bid1 = t1.calculate_platform_bid()
    bid2 = t2.calculate_platform_bid()
    assert bid1 > bid2, f"Expected T1 bid ({bid1}) to be higher than T2 bid ({bid2})"
    
    # 3. Release the occupant. This triggers the VCG auction!
    sur_station.release_platform("MOCK_OCCUPANT", None)
    
    # Verify that T1 got the platform and paid second-price
    assert t1.train_id in sur_station.occupied_platforms
    assert t2.train_id not in sur_station.occupied_platforms
    assert req1.triggered, "Winner's platform request should be triggered"
    assert not req2.triggered, "Loser's platform request should not be triggered"
    
    expected_payment = bid2
    assert abs(t1.priority_tokens - (100.0 - expected_payment)) < 1e-3, f"Expected T1 tokens to be {100.0 - expected_payment}, got {t1.priority_tokens}"
    assert abs(t1.bids_paid - expected_payment) < 1e-3, f"Expected T1 bids_paid to be {expected_payment}, got {t1.bids_paid}"
    
    print(f"Verified: Winner {t1.train_id} paid second-price {t1.bids_paid:.1f} tokens. Remaining: {t1.priority_tokens:.1f} tokens.")
    print("OK: Game-Theory Token Bidding passed.\n")

def test_electrical_voltage_degradation():
    print("Testing Electrical Voltage Degradation Physics...")
    engine = SimulationEngine()
    t = engine.trains[0]
    
    # Position train on MUM->TNA
    t.from_node = "MUM"
    t.to_node = "TNA"
    
    # Temporarily bypass substation limit trip
    engine.substation_limit = 1000.0
    
    # Modify segment distance in graph to allow longer travel distance
    edge_data = engine.topology.graph.get_edge_data("MUM", "TNA")
    orig_distance = edge_data["distance_km"]
    edge_data["distance_km"] = 500.0
    
    # Run a tiny bit to initialize the segment loop inside SimPy and enter the while loop
    engine.env.run(until=0.01)
    
    try:
        # Move train far down the track to induce high resistance
        t.traveled_distance_on_segment = 450.0
        t.speed_kmh = 270.0
        
        # Advance environment
        engine.env.run(until=0.11)
        
        # Verify voltage dropped below 22kV
        assert t.voltage < 22000.0, f"Expected voltage < 22kV, got {t.voltage:.1f}V"
        assert t.speed_kmh < 270.0, f"Expected speed to be scaled down, got {t.speed_kmh:.1f} km/h"
        print(f"OK: Voltage dropped to {t.voltage:.1f}V. Speed scaled down from 270 to {t.speed_kmh:.1f} km/h.")
    finally:
        # Restore distance
        edge_data["distance_km"] = orig_distance
        
    print("OK: Electrical Voltage Degradation Physics passed.\n")

def test_telemetry_packet_loss():
    print("Testing Telemetry Packet Loss Jitter...")
    engine = SimulationEngine()
    t = engine.trains[0]
    
    # Mock random.random to return 0.0, which is < 0.02 (guaranteeing packet loss)
    import random
    orig_random = random.random
    random.random = lambda: 0.0
    
    try:
        # Run simulation slightly
        engine.env.run(until=0.11)
        
        # Check that the train is throttled to 50 km/h or less due to telemetry loss
        assert t.speed_kmh <= 50.0, f"Train speed should be restricted to <= 50 km/h due to telemetry loss, got {t.speed_kmh}"
        print(f"OK: Telemetry loss throttle active: train speed restricted to {t.speed_kmh:.1f} km/h.")
    finally:
        random.random = orig_random
        
    print("OK: Telemetry Packet Loss Jitter passed.\n")

def test_token_starvation_prevention():
    print("Testing Token Starvation Prevention Tax...")
    engine = SimulationEngine()
    t = engine.trains[0]
    
    # Set the scheduled arrival at next station (TNA) in the past to simulate delay
    engine.scheduled_arrivals[(t.train_id, "TNA")] = -10.0
    initial_tokens = t.priority_tokens
    
    # Advance environment by 0.5 minutes (approx 5 ticks)
    engine.env.run(until=0.51)
    
    # Verify tokens increased
    assert t.priority_tokens > initial_tokens, f"Tokens should have increased, initial: {initial_tokens}, current: {t.priority_tokens}"
    print(f"OK: Tokens replenished from {initial_tokens:.1f} to {t.priority_tokens:.1f} over delayed ticks.")
    print("OK: Token Starvation Prevention Tax passed.\n")

def test_crossover_interlock_conflicts():
    print("Testing Catenary Track Crossover Interlock Conflicts...")
    engine = SimulationEngine()
    t = engine.trains[0]
    
    # Put train 0 on segment MUM->TNA, approaching TNA
    t.from_node = "MUM"
    t.to_node = "TNA"
    
    # Run a tiny bit to initialize the segment loop inside SimPy and enter the while loop
    engine.env.run(until=0.01)
    
    t.traveled_distance_on_segment = 27.0  # 1 km from TNA (total segment length is 28.0 km)
    
    # Lock crossover at destination station TNA
    engine.crossover_locks["TNA"] = engine.env.now + 5.0
    
    # Run environment a step to evaluate spacing headway
    engine.env.run(until=0.11)
    
    # The train is 1 km away from a locked crossover.
    # The ATC Braking Curve should restrict its speed.
    assert t.speed_kmh < 270.0, f"Expected speed to be throttled below 270 km/h due to crossover lock, got {t.speed_kmh}"
    print(f"OK: Crossover lock on TNA successfully throttled approaching train speed to {t.speed_kmh:.1f} km/h.")
    print("OK: Catenary Track Crossover Interlock Conflicts passed.\n")

def run_all_tests():
    import random
    import numpy as np
    random.seed(42)
    np.random.seed(42)
    test_simulation_initialization()
    test_detour_routing_mechanics()
    test_short_turn_mechanics()
    test_crew_roster_violation()
    test_monte_carlo_scenarios()
    test_dynamic_spacing_headways()
    test_axle_telemetry_ingest()
    test_non_linear_delay_cost()
    test_catenary_substation_solver()
    test_crew_depot_allocation_constraints()
    test_game_theory_token_bidding()
    test_electrical_voltage_degradation()
    test_telemetry_packet_loss()
    test_token_starvation_prevention()
    test_crossover_interlock_conflicts()
    print("All unit tests passed successfully!")

if __name__ == "__main__":
    run_all_tests()
