import sys
import os

# Add parent directory to path so python can import simulation package
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from simulation.engine import SimulationEngine
from simulation.agents import CrewAgent, TrainAgent

def test_simulation_initialization():
    print("Testing Simulation Initialization...")
    engine = SimulationEngine()
    assert len(engine.stations) == 12, f"Expected 12 stations, got {len(engine.stations)}"
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
            if t.train_id == "LC-901" and t.from_node == "SUR" and t.to_node == "BHA" and t.status == "RUNNING":
                detour_detected = True
                assert t.speed_kmh == 150.0, f"Expected detour speed of 150 km/h, got {t.speed_kmh}"
                break
        if detour_detected:
            break
            
    assert detour_detected, "LC-901 never reached SUR->BHA detour segment during the test window!"
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
        print(f"Scenario: {s['name']} | ORS: {s['resilience_score']} | Explainer: {s['explainer']}")
        
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

def run_all_tests():
    test_simulation_initialization()
    test_detour_routing_mechanics()
    test_short_turn_mechanics()
    test_crew_roster_violation()
    test_monte_carlo_scenarios()
    test_dynamic_spacing_headways()
    print("All unit tests passed successfully!")

if __name__ == "__main__":
    run_all_tests()
