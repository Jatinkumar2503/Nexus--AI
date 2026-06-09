import sys
import os

# Add parent directory to path so python can import simulation package
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from simulation.engine import SimulationEngine

def test_simulation_run():
    print("Initializing SimulationEngine...")
    engine = SimulationEngine()
    
    # Check that stations and trains are loaded
    assert len(engine.stations) > 0, "No station agents loaded!"
    assert len(engine.trains) > 0, "No train agents loaded!"
    print(f"Loaded {len(engine.stations)} stations and {len(engine.trains)} trains.")

    # Run for a few simulated minutes
    print("Stepping simulation forward by 5 simulated minutes...")
    engine.env.run(until=5.0)
    assert engine.env.now == 5.0, "Time did not advance correctly!"
    print(f"Simulation time is now {engine.get_sim_time_str()} ({engine.env.now} minutes)")

    # Inject disruption
    print("Injecting track disruption between Surat (SUR) and Bharuch (BHA)...")
    disruption = engine.inject_disruption(
        node_id=None,
        edge_id="SUR->BHA",
        duration=60,
        severity="HIGH",
        description="Signal failure at Surat-Bharuch segment"
    )
    assert len(engine.disruptions) == 1, "Disruption was not injected!"
    print(f"Disruption injected successfully: {disruption['description']}")

    # Evaluate scenarios
    print("Evaluating recovery scenarios...")
    scenarios = engine.evaluate_scenarios()
    assert len(scenarios) == 3, f"Expected 3 scenarios, got {len(scenarios)}"
    
    for s in scenarios:
        print(f"Scenario Option: {s['name']} (ORS: {s['resilience_score']})")
        print(f"  Delay minutes: {s['delay_minutes']}, Energy (kWh): {s['energy_cost_kwh']}, Crew violations: {s['crew_violations_count']}")
        print(f"  Negotiation logic: {s['explainer']}")
        assert s["resilience_score"] > 0, "Resilience score is invalid!"

    # Resolve scenario
    print("Resolving disruption by applying Detour strategy...")
    engine.resolve_scenario("detour")
    assert engine.active_recovery_strategy == "detour", "Scenario was not resolved!"
    print("Success: Test run passed.")

if __name__ == "__main__":
    test_simulation_run()
