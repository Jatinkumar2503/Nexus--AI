import logging
import time
from typing import Optional, List
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from simulation.topology import RailTopology
from simulation.engine import SimulationEngine
from simulation.models import SimulationStepResponse, Disruption, TrainState, StationState, SimulationMetrics, ScenarioOption

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("nexus-api")

app = FastAPI(
    title="NEXUS API",
    description="Backend API and Simulation Engine for NEXUS Rail Network Operations Simulator",
    version="1.0.0"
)

# Initialize rail network topology and SimPy simulation engine
topology = RailTopology()
engine = SimulationEngine()

# Set up CORS middleware for integration with the React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify the actual frontend origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ControlPayload(BaseModel):
    action: str  # "play", "pause", "reset", "step"
    speed: Optional[float] = 30.0

class DisruptionPayload(BaseModel):
    node_id: Optional[str] = None
    edge_id: Optional[str] = None
    duration: int
    severity: str = "HIGH"
    description: str

class ResolvePayload(BaseModel):
    strategy: str  # "do_nothing", "detour", "short_turn"

@app.get("/")
async def root():
    """API health-check root endpoint."""
    return {
        "status": "healthy",
        "service": "NEXUS Rail Operations Simulator API",
        "version": "1.0.0"
    }

@app.get("/api/health")
async def health():
    """Detailed health check endpoint."""
    return {
        "status": "ok",
        "components": {
            "api": "online",
            "simulation_engine": "initialized"
        }
    }

@app.get("/api/topology")
async def get_topology():
    """Fetch the rail network nodes and edges."""
    return {
        "status": "success",
        "nodes": topology.get_nodes(),
        "edges": topology.get_edges()
    }

@app.get("/api/live-trains")
async def get_live_trains():
    """Fetch the current position and status of all trains."""
    engine.update_clock()
    return {
        "status": "success",
        "simulation_time": engine.get_sim_time_str(),
        "trains": engine.get_active_trains()
    }

@app.get("/api/simulation/state", response_model=SimulationStepResponse)
async def get_simulation_state():
    """Fetch the full, detailed state of the running simulation."""
    engine.update_clock()
    
    # 1. Active trains
    trains_data = engine.get_active_trains()
    trains_list = []
    for t in trains_data:
        trains_list.append(TrainState(
            train_id=t["train_id"],
            service_type=t["service_type"],
            direction=t["direction"],
            current_node=t["current_node"],
            next_node=t["next_node"],
            speed_kmh=t["speed_kmh"],
            delay_minutes=t["delay_minutes"],
            passenger_count=t["passenger_count"],
            coordinates=t["coordinates"],
            status=t["status"],
            energy_consumed_kwh=t["energy_consumed_kwh"],
            crew_violated=t["crew_violated"]
        ))

    # 2. Station states
    stations_list = []
    for code, s in engine.stations.items():
        stations_list.append(StationState(
            station_id=s.station_id,
            name=s.name,
            occupied_platforms=s.occupied_platforms,
            capacity=s.platforms_count,
            queue=s.queue
        ))

    # 3. Active disruptions
    active_disruptions = []
    sim_now = engine.get_sim_time_minutes()
    for d in engine.disruptions:
        start = d.get("start_time", 0.0)
        duration = d.get("duration", 0)
        if start <= sim_now < (start + duration):
            active_disruptions.append(Disruption(
                id=d["id"],
                node_id=d.get("node_id"),
                edge_id=d.get("edge_id"),
                duration=d["duration"],
                severity=d["severity"],
                description=d["description"],
                start_time=d["start_time"]
            ))

    # 4. Global Metrics
    PRIORITY_WEIGHTS = {
        "Vande Bharat": 1.5,
        "Tejas Express": 1.2,
        "Local": 0.8
    }
    total_delay = sum(
        t.delay_minutes * t.passenger_count * PRIORITY_WEIGHTS.get(t.service_type, 1.0)
        for t in trains_list
    ) / 500.0
    total_energy = sum(t.energy_consumed_kwh for t in trains_list)
    crew_violations = sum(1 for t in engine.trains if t.crew.check_violation(sim_now, 0.0))
    
    # Composite ORS Score
    delay_penalty = (total_delay / 240.0) * 20
    energy_penalty = (max(0.0, total_energy - 5000.0) / 2000.0) * 15
    crew_penalty = crew_violations * 30
    ors = max(5.0, min(100.0, 100.0 - delay_penalty - energy_penalty - crew_penalty))

    metrics = SimulationMetrics(
        total_passenger_delay_minutes=round(total_delay, 1),
        total_energy_kwh=round(total_energy, 1),
        crew_violation_count=crew_violations,
        resilience_score=round(ors, 1)
    )

    return SimulationStepResponse(
        simulation_time=engine.get_sim_time_str(),
        trains=trains_list,
        stations=stations_list,
        active_disruptions=active_disruptions,
        metrics=metrics,
        negotiation_logs=engine.negotiation_logs
    )

@app.post("/api/simulation/control")
async def control_simulation(payload: ControlPayload):
    """Play, pause, reset, or step the simulation clock."""
    global engine
    if payload.action == "play":
        engine.isPlaying = True
        engine.last_update_real_time = time.time()
        if payload.speed:
            engine.sim_speed_multiplier = payload.speed
    elif payload.action == "pause":
        engine.isPlaying = False
    elif payload.action == "reset":
        engine = SimulationEngine()
    elif payload.action == "step":
        engine.isPlaying = False
        try:
            engine.env.run(until=engine.env.now + 1.0)
        except Exception:
            pass
    return {
        "status": "success",
        "isPlaying": engine.isPlaying,
        "speed": engine.sim_speed_multiplier
    }

@app.post("/api/disruption/inject")
async def inject_disruption(payload: DisruptionPayload):
    """Inject a network blockage disruption."""
    disp = engine.inject_disruption(
        node_id=payload.node_id,
        edge_id=payload.edge_id,
        duration=payload.duration,
        severity=payload.severity,
        description=payload.description
    )
    return {"status": "success", "disruption": disp}

@app.get("/api/scenarios/compare")
async def compare_scenarios():
    """Trigger parallel simulations to compare recovery strategies."""
    scenarios_data = engine.evaluate_scenarios()
    scenarios_list = []
    for s in scenarios_data:
        scenarios_list.append(ScenarioOption(
            id=s["id"],
            name=s["name"],
            description=s["description"],
            delay_minutes=s["delay_minutes"],
            energy_cost_kwh=s["energy_cost_kwh"],
            crew_violations_count=s["crew_violations_count"],
            is_legal=s["is_legal"],
            resilience_score=s["resilience_score"],
            explainer=s["explainer"]
        ))
    return {"status": "success", "scenarios": scenarios_list}

@app.post("/api/scenarios/resolve")
async def resolve_scenario(payload: ResolvePayload):
    """Commit a chosen recovery strategy to the running simulation."""
    engine.resolve_scenario(payload.strategy)
    return {"status": "success", "strategy": payload.strategy}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
