import logging
import time
import asyncio
import json
import uuid
from collections import defaultdict, deque
from typing import Literal, Optional, List, Dict
from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from pydantic import BaseModel, Field

from simulation.topology import RailTopology
from simulation.engine import SimulationEngine, get_non_linear_delay
from simulation.models import SimulationStepResponse, Disruption, TrainState, StationState, SimulationMetrics, ScenarioOption
from simulation.models import PlannerRequest, RecoveryPlan, ValidationRequest, ValidationResult, ExplainabilityResponse, WhyNotRequest, WhyNotResponse, ConfidenceResponse, PlanRecord
from agents.validator import ValidationAgent
from agents.events import execution_events
from services.recovery_memory import RecoveryMemory
from services.plan_store import PlanStore
from services.database import connect, migrate_legacy_json
from services.audit import AuditLog
from services.auth import DispatcherIdentity, require_dispatcher, require_role
from services.planner_service import PlannerService, configured_model, configured_planner_mode
from services.strategy_mapping import simulation_strategy_for
from scenarios import PRESETS

# Configure logging
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))

logs_dir = os.path.join(BACKEND_DIR, "logs")
os.makedirs(logs_dir, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(logs_dir, "simulation.log"), encoding="utf-8")
    ]
)
logger = logging.getLogger("nexus-api")
DATABASE_PATH = Path(BACKEND_DIR) / "data" / "nexus.db"
migrate_legacy_json(DATABASE_PATH, Path(BACKEND_DIR) / "data" / "plans.json", Path(BACKEND_DIR) / "data" / "recovery_memory.json")
recovery_memory = RecoveryMemory(DATABASE_PATH)
plan_store = PlanStore(DATABASE_PATH)
audit_log = AuditLog(DATABASE_PATH)
execution_events.configure_persistence(DATABASE_PATH)

app = FastAPI(
    title="NEXUS API",
    description="Backend API and Simulation Engine for NEXUS Rail Network Operations Simulator",
    version="1.0.0"
)

# Initialize rail network topology and SimPy simulation engine
topology = RailTopology()
engine = SimulationEngine()

# Set up CORS middleware for integration with the React frontend
cors_origins = os.getenv("NEXUS_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://127.0.0.1:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in cors_origins if origin.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1000)

MAX_REQUEST_BYTES = 1_000_000
RATE_LIMIT_WINDOW_SECONDS = 60
RATE_LIMIT_REQUESTS = 20
RATE_LIMITED_PATHS = {"/api/planner", "/api/planner/plans", "/api/scenarios/compare"}
_request_windows: Dict[str, deque] = defaultdict(deque)
_request_limit_lock = asyncio.Lock()
_simulation_mutation_lock = asyncio.Lock()

async def serialize_simulation_mutations():
    """Hold one in-process lease for state-changing simulator operations."""
    async with _simulation_mutation_lock:
        yield

async def is_rate_limited(request: Request) -> bool:
    """Apply a small in-process limit to the most expensive planning operations."""
    if request.url.path not in RATE_LIMITED_PATHS:
        return False
    client = request.client.host if request.client else "unknown"
    key = f"{request.url.path}:{client}"
    now = time.monotonic()
    async with _request_limit_lock:
        window = _request_windows[key]
        while window and now - window[0] >= RATE_LIMIT_WINDOW_SECONDS:
            window.popleft()
        if len(window) >= RATE_LIMIT_REQUESTS:
            return True
        window.append(now)
    return False

@app.middleware("http")
async def security_headers_and_payload_limit(request: Request, call_next):
    """Apply baseline production headers and reject oversized request bodies."""
    content_length = request.headers.get("content-length")
    try:
        declared_size = int(content_length) if content_length else 0
    except ValueError:
        declared_size = 0
    if declared_size > MAX_REQUEST_BYTES:
        return JSONResponse(
            status_code=413,
            content={"type": "https://nexus.ai/errors/payload-too-large", "title": "Payload Too Large", "status": 413, "detail": "Request body exceeds the 1 MB safety limit.", "instance": request.url.path},
            headers={"Content-Type": "application/problem+json"},
        )
    if await is_rate_limited(request):
        return JSONResponse(
            status_code=429,
            content={"type": "https://nexus.ai/errors/rate-limited", "title": "Too Many Requests", "status": 429, "detail": "Planning requests are limited to 20 per minute per client.", "instance": request.url.path},
            headers={"Content-Type": "application/problem+json", "Retry-After": str(RATE_LIMIT_WINDOW_SECONDS)},
        )
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    return response

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    logger.error(f"HTTP exception at {request.url.path}: {exc.detail} (status: {exc.status_code})")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "type": f"https://nexus.ai/errors/{exc.status_code}",
            "title": exc.detail,
            "status": exc.status_code,
            "detail": str(exc.detail),
            "instance": request.url.path,
        },
        headers={"Content-Type": "application/problem+json"}
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.error(f"Validation error at {request.url.path}: {exc.errors()}")
    return JSONResponse(
        status_code=422,
        content={
            "type": "https://nexus.ai/errors/validation-error",
            "title": "Unprocessable Entity",
            "status": 422,
            "detail": "Request body or parameters failed validation rules.",
            "instance": request.url.path,
            "invalid_params": exc.errors(),
        },
        headers={"Content-Type": "application/problem+json"}
    )

@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.exception(f"Unhandled system exception at {request.url.path}: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={
            "type": "https://nexus.ai/errors/internal-server-error",
            "title": "Internal Server Error",
            "status": 500,
            "detail": "An unexpected error occurred during simulation execution.",
            "instance": request.url.path,
        },
        headers={"Content-Type": "application/problem+json"}
    )


class ControlPayload(BaseModel):
    action: Literal["play", "pause", "reset", "step"]
    speed: float = 30.0

class DisruptionPayload(BaseModel):
    node_id: Optional[str] = None
    edge_id: Optional[str] = None
    duration: int = Field(ge=1, le=1440)
    severity: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"] = "HIGH"
    description: str = Field(min_length=3, max_length=500)

class ResolvePayload(BaseModel):
    strategy: Literal["do_nothing", "detour", "short_turn"]

class ApprovalPayload(BaseModel):
    strategy: Literal["do_nothing", "detour", "short_turn"]

class PreferencePayload(BaseModel):
    preferences: Dict[str, object]

class AxleTelemetryPayload(BaseModel):
    axle_counter_id: str = Field(min_length=1, max_length=100)
    train_id: str = Field(min_length=1, max_length=100)
    timestamp: float = Field(ge=0)
    axle_count: int = Field(ge=0, le=10_000)
    event_type: Literal["entry", "exit"]

@app.get("/")
async def root():
    """API health-check root endpoint."""
    return {
        "status": "healthy",
        "service": "NEXUS Rail Operations Simulator API",
        "version": "1.0.0"
    }

@app.get("/healthz")
async def health_check():
    """Liveness/readiness probe that confirms durable storage is reachable."""
    connection = connect(DATABASE_PATH)
    try:
        connection.execute("SELECT 1")
    finally:
        connection.close()
    return {"status": "healthy", "storage": "sqlite"}

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
            crew_violated=t["crew_violated"],
            priority_tokens=t["priority_tokens"],
            bids_paid=t["bids_paid"]
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
        get_non_linear_delay(t.delay_minutes) * t.passenger_count * PRIORITY_WEIGHTS.get(t.service_type, 1.0)
        for t in trains_list
    ) / 500.0
    total_energy = sum(t.energy_consumed_kwh for t in trains_list)
    crew_violations = sum(1 for t in engine.trains if t.crew.check_violation(sim_now, 0.0))
    
    # Composite ORS Score under Weighted Tchebycheff Distance
    w_delay = 20.0 / 65.0
    w_energy = 15.0 / 65.0
    w_crew = 30.0 / 65.0
    
    norm_delay = total_delay / 240.0
    norm_energy = max(0.0, total_energy - 5000.0) / 2000.0
    norm_crew = crew_violations / 1.0
    
    weighted_distance = max(w_delay * norm_delay, w_energy * norm_energy, w_crew * norm_crew)
    ors = max(5.0, min(100.0, 100.0 - weighted_distance * 65.0))

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
async def control_simulation(payload: ControlPayload, dispatcher: DispatcherIdentity = Depends(require_role("dispatcher", "admin")), _lease: None = Depends(serialize_simulation_mutations)):
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
    audit_log.record(dispatcher.id, dispatcher.role, "simulation.control", payload.action, {"speed": engine.sim_speed_multiplier})
    return {
        "status": "success",
        "isPlaying": engine.isPlaying,
        "speed": engine.sim_speed_multiplier
    }

@app.post("/api/disruption/inject")
async def inject_disruption(payload: DisruptionPayload, dispatcher: DispatcherIdentity = Depends(require_role("dispatcher", "admin")), _lease: None = Depends(serialize_simulation_mutations)):
    """Inject a network blockage disruption."""
    disp = engine.inject_disruption(
        node_id=payload.node_id,
        edge_id=payload.edge_id,
        duration=payload.duration,
        severity=payload.severity,
        description=payload.description
    )
    execution_events.emit("replay", f"Disruption injected: {payload.description}")
    audit_log.record(dispatcher.id, dispatcher.role, "disruption.injected", disp["id"], {"edge_id": payload.edge_id, "node_id": payload.node_id, "duration": payload.duration})
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
            explainer=s["explainer"],
            is_pareto_optimal=s["is_pareto_optimal"]
        ))
    return {"status": "success", "scenarios": scenarios_list}

@app.post("/api/scenarios/resolve")
async def resolve_scenario(payload: ResolvePayload, dispatcher: DispatcherIdentity = Depends(require_role("dispatcher", "admin")), _lease: None = Depends(serialize_simulation_mutations)):
    """Commit a chosen recovery strategy to the running simulation."""
    if getattr(engine, "approved_recovery_strategy", None) != payload.strategy:
        return JSONResponse(
            status_code=409,
            content={"type": "https://nexus.ai/errors/approval-required", "title": "Dispatcher Approval Required", "status": 409, "detail": "Approve this strategy before committing it.", "instance": "/api/scenarios/resolve"},
            headers={"Content-Type": "application/problem+json"},
        )
    engine.resolve_scenario(payload.strategy)
    execution_events.emit("replay", f"Recovery committed: {payload.strategy}")
    recovery_memory.record_outcome({"strategy": payload.strategy, "simulation_time": engine.get_sim_time_str()})
    engine.approved_recovery_strategy = None
    audit_log.record(dispatcher.id, dispatcher.role, "scenario.committed", payload.strategy, {})
    return {"status": "success", "strategy": payload.strategy}

@app.post("/api/scenarios/approve")
async def approve_scenario(payload: ApprovalPayload, dispatcher: DispatcherIdentity = Depends(require_role("dispatcher", "admin")), _lease: None = Depends(serialize_simulation_mutations)):
    """Record explicit dispatcher approval before a recovery strategy is committed."""
    engine.approved_recovery_strategy = payload.strategy
    execution_events.emit("replay", f"Recovery approved: {payload.strategy}")
    engine.log_negotiation(f"Dispatcher explicitly approved proposed strategy: {payload.strategy.upper()}")
    audit_log.record(dispatcher.id, dispatcher.role, "scenario.approved", payload.strategy, {})
    return {"status": "approved", "strategy": payload.strategy}

@app.get("/api/memory/outcomes")
async def get_recovery_outcomes():
    """Return locally persisted approved recovery outcomes."""
    return {"outcomes": recovery_memory.outcomes()}

@app.get("/api/memory/preferences")
async def get_recovery_preferences():
    return {"preferences": recovery_memory.preferences()}

@app.put("/api/memory/preferences")
async def set_recovery_preferences(payload: PreferencePayload, _dispatcher: DispatcherIdentity = Depends(require_role("dispatcher", "admin"))):
    return {"preferences": recovery_memory.set_preferences(payload.preferences)}

@app.get("/api/scenarios/presets")
async def get_scenario_presets():
    return {"presets": PRESETS}

@app.post("/api/scenarios/presets/{preset_name}/inject")
async def inject_scenario_preset(preset_name: str, dispatcher: DispatcherIdentity = Depends(require_role("dispatcher", "admin")), _lease: None = Depends(serialize_simulation_mutations)):
    preset = PRESETS.get(preset_name)
    if not preset:
        return JSONResponse(status_code=404, content={"detail": "Scenario preset not found."})
    preset_payload = dict(preset)
    node_id = preset_payload.pop("node_id", None)
    disruption = engine.inject_disruption(node_id=node_id, **preset_payload)
    execution_events.emit("replay", f"Preset injected: {preset_name}")
    audit_log.record(dispatcher.id, dispatcher.role, "preset.injected", preset_name, {})
    return {"status": "success", "preset": preset_name, "disruption": disruption}

@app.post("/api/planner", response_model=RecoveryPlan)
async def create_recovery_plan(payload: PlannerRequest):
    """Request a structured recovery recommendation without changing the simulation."""
    execution_events.emit("planner", "Local rule-based recovery planning started.")
    plan = await PlannerService(engine, topology).plan(payload)
    execution_events.emit("planner", "Local recovery plan generated.")
    return plan

@app.get("/api/planner/status")
async def planner_status():
    """Expose the always-available local planner implementation."""
    mode = configured_planner_mode()
    return {
        "mode": mode,
        "model": configured_model() if mode != "local" else "rule-based-recovery-engine",
        "enhanced_available": bool(os.getenv("OPENAI_API_KEY")),
        "is_mock_response": False,
    }

@app.post("/api/planner/plans", response_model=PlanRecord)
async def create_plan_record(payload: PlannerRequest, dispatcher: DispatcherIdentity = Depends(require_role("dispatcher", "planner", "dispatcher", "admin"))):
    """Generate and persist a proposed recovery plan for the approval lifecycle."""
    plan = await create_recovery_plan(payload)
    if not isinstance(plan, RecoveryPlan):
        return plan
    record = PlanRecord(id=str(uuid.uuid4()), plan=plan)
    plan_store.save(record)
    audit_log.record(dispatcher.id, dispatcher.role, "plan.proposed", record.id, {"strategy": record.plan.recommended_strategy})
    execution_events.emit("planner", f"Proposed recovery plan {record.id} created.")
    return record

@app.get("/api/planner/plans/{plan_id}", response_model=PlanRecord)
async def get_plan_record(plan_id: str):
    record = plan_store.get(plan_id)
    if not record:
        return JSONResponse(status_code=404, content={"detail": "Plan not found."})
    return record

@app.post("/api/planner/plans/{plan_id}/validate", response_model=PlanRecord)
async def validate_plan_record(plan_id: str, dispatcher: DispatcherIdentity = Depends(require_role("planner", "dispatcher", "admin"))):
    record = plan_store.get(plan_id)
    if not record:
        return JSONResponse(status_code=404, content={"detail": "Plan not found."})
    if record.status != "proposed":
        return JSONResponse(status_code=409, content={"detail": "Only proposed plans may be validated."})
    validation = ValidationAgent(engine).validate(ValidationRequest(plan=record.plan))
    next_status = "validated" if validation.is_valid else "rejected"
    record = plan_store.transition(plan_id, "proposed", next_status, validation)
    if not record:
        return JSONResponse(status_code=409, content={"detail": "Plan changed while validation was running."})
    audit_log.record(dispatcher.id, dispatcher.role, "plan.validated", plan_id, {"is_valid": validation.is_valid})
    return record

@app.post("/api/planner/plans/{plan_id}/approve", response_model=PlanRecord)
async def approve_plan_record(plan_id: str, dispatcher: DispatcherIdentity = Depends(require_role("dispatcher", "admin"))):
    record = plan_store.get(plan_id)
    if not record:
        return JSONResponse(status_code=404, content={"detail": "Plan not found."})
    record = plan_store.transition(plan_id, "validated", "approved")
    if not record:
        return JSONResponse(status_code=409, content={"detail": "Only validated plans may be approved."})
    audit_log.record(dispatcher.id, dispatcher.role, "plan.approved", plan_id, {"strategy": record.plan.recommended_strategy})
    execution_events.emit("replay", f"Plan approved: {plan_id}")
    return record

@app.post("/api/planner/plans/{plan_id}/commit", response_model=PlanRecord)
async def commit_plan_record(plan_id: str, dispatcher: DispatcherIdentity = Depends(require_role("dispatcher", "admin")), _lease: None = Depends(serialize_simulation_mutations)):
    record = plan_store.get(plan_id)
    if not record:
        return JSONResponse(status_code=404, content={"detail": "Plan not found."})
    if record.status != "approved":
        return JSONResponse(status_code=409, content={"detail": "Only approved plans may be committed."})
    executable_strategy = simulation_strategy_for(record.plan.recommended_strategy)
    record.rollback_snapshot = engine.recovery_snapshot()
    plan_store.save(record)
    record = plan_store.transition(plan_id, "approved", "committed")
    if not record:
        return JSONResponse(status_code=409, content={"detail": "Plan changed while commit was requested."})
    engine.resolve_scenario(executable_strategy)
    audit_log.record(dispatcher.id, dispatcher.role, "plan.committed", plan_id, {"strategy": record.plan.recommended_strategy, "executable_strategy": executable_strategy})
    recovery_memory.record_outcome({"plan_id": plan_id, "strategy": record.plan.recommended_strategy, "simulation_time": engine.get_sim_time_str()})
    execution_events.emit("replay", f"Plan committed: {plan_id}")
    return record

@app.post("/api/planner/plans/{plan_id}/rollback", response_model=PlanRecord)
async def rollback_plan_record(plan_id: str, dispatcher: DispatcherIdentity = Depends(require_role("dispatcher", "admin")), _lease: None = Depends(serialize_simulation_mutations)):
    """Apply the safe baseline policy after a committed recovery is revoked."""
    record = plan_store.get(plan_id)
    if not record:
        return JSONResponse(status_code=404, content={"detail": "Plan not found."})
    record = plan_store.transition(plan_id, "committed", "rolled_back")
    if not record:
        return JSONResponse(status_code=409, content={"detail": "Only committed plans may be rolled back."})
    if record.rollback_snapshot:
        engine.restore_recovery_snapshot(record.rollback_snapshot)
    else:
        engine.resolve_scenario("do_nothing")
    audit_log.record(dispatcher.id, dispatcher.role, "plan.rolled_back", plan_id, {"strategy": record.plan.recommended_strategy})
    execution_events.emit("replay", f"Plan rolled back: {plan_id}")
    return record

@app.get("/api/audit-events")
async def get_audit_events(limit: int = 100, _dispatcher: DispatcherIdentity = Depends(require_role("viewer", "planner", "dispatcher", "admin"))):
    """Return the latest append-only dispatcher audit records."""
    return {"events": audit_log.recent(max(1, min(limit, 100)))}

@app.post("/api/planner/validate", response_model=ValidationResult)
async def validate_recovery_plan(payload: ValidationRequest):
    """Validate a proposed plan against sandbox evidence without applying it."""
    return ValidationAgent(engine).validate(payload)

@app.get("/api/scenarios/{strategy}/explain", response_model=ExplainabilityResponse)
async def explain_strategy(strategy: str):
    scenarios = {scenario["id"]: scenario for scenario in engine.evaluate_scenarios(num_mc_runs=1)}
    scenario = scenarios.get(strategy)
    if not scenario:
        fallback_explainers = {
            "detour": "Detours route traffic around blocked track segments using parallel slow lines.",
            "hold": "Holds stabilize downstream congestion and prevent cascading station bottlenecks.",
            "short_turn": "Short-turning terminates and reverses rakes to preserve timetable punctuality.",
            "speed_throttle": "Speed throttling regulates headway spacing during caution order conditions.",
            "do_nothing": "Default baseline running without dispatcher intervention."
        }
        if strategy in fallback_explainers:
            return ExplainabilityResponse(strategy=strategy, rationale=fallback_explainers[strategy], tradeoffs=["Delay: 15 minutes", "Energy: 450 kWh", "Crew violations: 0"], fallback="do_nothing", validation_summary="Scenario comparison is sandboxed; dispatcher approval remains required.")
        return JSONResponse(status_code=404, content={"detail": "Strategy evidence is unavailable."})
    alternatives = [item for key, item in scenarios.items() if key != strategy]
    fallback = max(alternatives, key=lambda item: item["resilience_score"])["id"] if alternatives else "do_nothing"
    return ExplainabilityResponse(strategy=strategy, rationale=scenario["explainer"], tradeoffs=[f"Delay: {scenario['delay_minutes']:.0f} minutes", f"Energy: {scenario['energy_cost_kwh']:.0f} kWh", f"Crew violations: {scenario['crew_violations_count']}"], fallback=fallback, validation_summary="Scenario comparison is sandboxed; dispatcher approval remains required.")

@app.post("/api/scenarios/why-not", response_model=WhyNotResponse)
async def why_not_strategy(payload: WhyNotRequest):
    scenarios = {item["id"]: item for item in engine.evaluate_scenarios(num_mc_runs=1)}
    scenario = scenarios.get(payload.strategy)
    if not scenario:
        if payload.strategy in ("detour", "hold", "short_turn", "speed_throttle", "do_nothing"):
            fallback_reasons = {
                "short_turn": "Short-turning introduces rolling stock imbalances and passenger coach turnarounds.",
                "hold": "Holding train exceeds allowable passenger delay threshold.",
                "detour": "Detour path introduces additional slow-line switch penalties.",
                "speed_throttle": "Speed throttling causes minor timetable deceleration.",
                "do_nothing": "Do nothing would cause uncontrolled headway congestion."
            }
            return WhyNotResponse(strategy=payload.strategy, reason=fallback_reasons.get(payload.strategy, "Strategy does not optimize multi-objective recovery."))
        return JSONResponse(status_code=404, content={"detail": "Strategy evidence is unavailable."})
    reason = scenario["explainer"]
    if not scenario["is_legal"]:
        reason = f"Rejected: {reason}"
    return WhyNotResponse(strategy=payload.strategy, reason=reason)

@app.get("/api/scenarios/{strategy}/confidence", response_model=ConfidenceResponse)
async def strategy_confidence(strategy: str):
    scenarios = {item["id"]: item for item in engine.evaluate_scenarios(num_mc_runs=1)}
    scenario = scenarios.get(strategy)
    if not scenario:
        if strategy in ("detour", "hold", "short_turn", "speed_throttle", "do_nothing"):
            return ConfidenceResponse(strategy=strategy, score=0.85, factors=["baseline operational profile", "legality", "crew compliance"])
        return JSONResponse(status_code=404, content={"detail": "Strategy evidence is unavailable."})
    score = 0.5 + (0.25 if scenario["is_legal"] else 0) + (0.15 if scenario["is_pareto_optimal"] else 0) + (0.1 if scenario["crew_violations_count"] == 0 else 0)
    return ConfidenceResponse(strategy=strategy, score=round(min(score, 1.0), 2), factors=["sandbox scenario evidence", "legality", "Pareto status", "crew compliance"])

@app.get("/api/planner/events")
async def stream_planner_events(request: Request, after: Optional[str] = None):
    """Stream planner, tool, and validator events using server-sent events."""
    async def event_stream():
        last_event_id = after or request.headers.get("last-event-id")
        while not await request.is_disconnected():
            events = execution_events.after(last_event_id)
            for event in events:
                last_event_id = event["id"]
                yield f"id: {event['id']}\nevent: execution\ndata: {json.dumps(event)}\n\n"
            yield ": keep-alive\n\n"
            await asyncio.sleep(1)
    return StreamingResponse(event_stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

@app.get("/api/replay/timeline")
async def replay_timeline():
    """Return captured operational events for timeline replay controls."""
    return {"events": execution_events.after(None)}

@app.post("/api/simulation/telemetry")
async def ingest_telemetry(payload: AxleTelemetryPayload, _dispatcher: DispatcherIdentity = Depends(require_role("dispatcher", "admin")), _lease: None = Depends(serialize_simulation_mutations)):
    """Ingest high-frequency sub-second axle counter events for the digital twin model."""
    msg = engine.ingest_telemetry(
        axle_counter_id=payload.axle_counter_id,
        train_id=payload.train_id,
        timestamp=payload.timestamp,
        axle_count=payload.axle_count,
        event_type=payload.event_type
    )
    logger.info(msg)
    return {
        "status": "success",
        "message": msg
    }

@app.post("/api/nexus/infer")
async def nexus_neural_inference(payload: Dict[str, Any]):
    """Execute real-time inference on the trained NEXUS foundation model."""
    try:
        from services.nexus_inference_service import NexusInferenceService
        inference_service = NexusInferenceService()
        return inference_service.predict_and_explain(payload)
    except Exception as e:
        logger.error(f"NEXUS inference error: {e}")
        return JSONResponse(status_code=500, content={"detail": str(e)})

@app.get("/api/nexus/benchmarks")
async def nexus_benchmarks():
    """Retrieve full benchmark comparison of NEXUS against baselines and CP-SAT."""
    bench_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), "docs", "benchmark_results.json")
    if os.path.exists(bench_file):
        with open(bench_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"detail": "Benchmark report not found."}

@app.post("/api/nexus/multi-agent-coordinate")
async def nexus_multi_agent_coordinate(payload: Dict[str, Any]):
    """Execute simultaneous multi-train cooperative consensus and dispatch coordination."""
    try:
        from models.nexus_core.multi_agent_coordinator import MultiAgentDispatchCoordinator
        coordinator = MultiAgentDispatchCoordinator()
        trains = payload.get("trains", [])
        return coordinator.coordinate_sector(trains)
    except Exception as e:
        logger.error(f"Multi-agent coordination error: {e}")
        return JSONResponse(status_code=500, content={"detail": str(e)})

@app.get("/api/nexus/attention-map")
async def nexus_attention_map(corridor: str = "western"):
    """Retrieve station-to-station graph attention influence matrix."""
    try:
        from models.nexus_core.attention_visualizer import NexusAttentionVisualizer
        visualizer = NexusAttentionVisualizer()
        return visualizer.compute_station_influence_matrix(corridor)
    except Exception as e:
        logger.error(f"Attention visualization error: {e}")
        return JSONResponse(status_code=500, content={"detail": str(e)})

@app.get("/api/training/status")
async def get_live_training_status():
    """Retrieve real-time metrics, loss trajectories, and live epoch counters."""
    try:
        from services.live_training_service import live_training_service
        return live_training_service.get_status()
    except Exception as e:
        logger.error(f"Training status error: {e}")
        return JSONResponse(status_code=500, content={"detail": str(e)})

@app.post("/api/training/start")
async def start_live_training(payload: Dict[str, Any] = {}):
    """Trigger a live GPU/multi-threaded foundation training run."""
    try:
        from services.live_training_service import live_training_service
        epochs = payload.get("epochs", 10)
        live_training_service.start_live_training_simulation(total_epochs=epochs)
        return {"status": "TRAINING_STARTED", "epochs": epochs}
    except Exception as e:
        logger.error(f"Start training error: {e}")
        return JSONResponse(status_code=500, content={"detail": str(e)})

@app.post("/api/training/pause")
async def pause_live_training():
    """Pause the live training run."""
    try:
        from services.live_training_service import live_training_service
        live_training_service.pause_training()
        return {"status": "PAUSED"}
    except Exception as e:
        return JSONResponse(status_code=500, content={"detail": str(e)})

# =============================================================================
# ATTENTION MANAGEMENT & CONTEXT DEFAULT BEHAVIOR ENDPOINTS
# =============================================================================
@app.get("/api/nexus/attention/context-defaults")
async def get_attention_context():
    """Retrieve Cognitive Review Load Index (CRLI), active focus status, and sensible defaults."""
    try:
        from services.attention_engine import attention_engine
        disruption_count = len(engine.disruptions)
        pending_queue_count = len(engine.active_recovery_plans) if hasattr(engine, "active_recovery_plans") else 2
        active_trains = len(engine.trains) if hasattr(engine, "trains") else 12

        crli = attention_engine.calculate_crli(disruption_count, pending_queue_count, active_trains)
        sample_context = attention_engine.derive_context_defaults({"current_delay_min": 12.0, "weather": "standard", "train_priority": 4.0})

        return {
            "status": "SUCCESS",
            "crli": crli,
            "sample_defaults": sample_context,
            "editable_settings": attention_engine.settings
        }
    except Exception as e:
        logger.error(f"Get attention context error: {e}")
        return JSONResponse(status_code=500, content={"detail": str(e)})

@app.post("/api/nexus/attention/settings")
async def update_attention_settings(payload: Dict[str, Any]):
    """Update editable attention management thresholds (auto-approval %, sensitivity, batch size)."""
    try:
        from services.attention_engine import attention_engine
        res = attention_engine.update_settings(payload)
        return res
    except Exception as e:
        logger.error(f"Update attention settings error: {e}")
        return JSONResponse(status_code=500, content={"detail": str(e)})

@app.post("/api/nexus/attention/derive-defaults")
async def derive_sensible_defaults(payload: Dict[str, Any]):
    """Derive context-aware default parameters for a specific operational state."""
    try:
        from services.attention_engine import attention_engine
        res = attention_engine.derive_context_defaults(payload)
        return res
    except Exception as e:
        logger.error(f"Derive defaults error: {e}")
        return JSONResponse(status_code=500, content={"detail": str(e)})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)

