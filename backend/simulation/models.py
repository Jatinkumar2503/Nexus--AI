from pydantic import BaseModel, Field
from typing import Any, List, Optional, Dict, Literal

class Disruption(BaseModel):
    id: str = Field(..., description="Unique identifier for the disruption event")
    node_id: Optional[str] = Field(None, description="The station node ID where failure occurs")
    edge_id: Optional[str] = Field(None, description="The track segment block ID where failure occurs")
    duration: int = Field(..., description="Duration of the disruption in minutes")
    severity: str = Field(..., description="Severity class: LOW, MEDIUM, HIGH, CRITICAL")
    description: Optional[str] = Field(None, description="Detailed explanation of the failure")
    start_time: float = Field(0.0, description="Start time of disruption in minutes from simulation start")

class TrainState(BaseModel):
    train_id: str
    service_type: str
    direction: str
    current_node: str
    next_node: str
    speed_kmh: float
    delay_minutes: float
    passenger_count: int
    coordinates: List[float] = Field(..., description="[Latitude, Longitude] representing spatial coordinates")
    status: str = Field("RUNNING", description="RUNNING, DWELLING, DELAYED, WAITING, TERMINATED")
    energy_consumed_kwh: float
    crew_violated: bool = Field(False, description="True if train crew shift limit is violated or predicted to be violated")
    priority_tokens: float = Field(100.0, description="Virtual game-theoretic priority tokens balance")
    bids_paid: float = Field(0.0, description="Total tokens spent during auctions")
    telemetry_packet_lost: bool = Field(False, description="True when telemetry packets are missing")
    voltage: Optional[float] = Field(None, description="Current overhead-line voltage in volts")

class StationState(BaseModel):
    station_id: str
    name: str
    occupied_platforms: List[str]
    capacity: int
    queue: List[str]

class ScenarioOption(BaseModel):
    id: str
    name: str
    description: str
    delay_minutes: float
    energy_cost_kwh: float
    crew_violations_count: int
    is_legal: bool = True
    resilience_score: float
    explainer: str
    is_pareto_optimal: bool = True

class SimulationMetrics(BaseModel):
    total_passenger_delay_minutes: float
    total_energy_kwh: float
    crew_violation_count: int
    resilience_score: float

class SimulationStepResponse(BaseModel):
    simulation_time: str
    trains: List[TrainState]
    stations: List[StationState]
    active_disruptions: List[Disruption]
    metrics: SimulationMetrics
    negotiation_logs: List[str]


class RecoveryAction(BaseModel):
    train_id: str = Field(..., description="ID of the train target for this action")
    action_type: Literal["detour", "short_turn", "hold", "speed_throttle", "crew_swap", "inspection", "reduce_acceleration", "priority_dispatch"] = Field(..., description="Allowed recovery action")
    location: str = Field(..., description="The node ID or edge ID where the action takes place")
    hold_duration_minutes: Optional[int] = Field(0, description="Duration in minutes if action is hold")
    routing_path: Optional[List[str]] = Field(None, description="Sequence of station node IDs for detours/short-turns")
    rationale: Optional[str] = Field(None, description="Operating rule that produced this action")

class ExpectedMetrics(BaseModel):
    delay_minutes: float = Field(..., description="Estimated aggregate delay minutes")
    energy_kwh: float = Field(..., description="Estimated energy consumption in kWh")
    crew_violations: int = Field(..., description="Estimated number of crew shift violations")
    resilience_score: float = Field(..., description="Estimated composite resilience score")

class PlannerMetadata(BaseModel):
    """Auditable planner details that never include secrets or raw prompts."""
    mode: Literal["local", "enhanced"] = "local"
    provider: Literal["local", "openai"] = "local"
    model: Optional[str] = None
    latency_ms: Optional[int] = None
    execution_time_ms: int = 0
    tool_calls: int = Field(0, ge=0)
    fallback_reason: Optional[str] = None

class StrategyAlternative(BaseModel):
    strategy: str
    rationale: str
    tradeoff: str
    rank: int = Field(ge=1)

class RecoveryPlan(BaseModel):
    recommended_strategy: Literal["do_nothing", "detour", "short_turn", "hold", "reroute", "reroute_and_prioritize", "crew_swap", "inspection", "mixed_strategy"] = Field(..., description="Allowed strategy")
    confidence_score: float = Field(..., ge=0.0, le=100.0, description="Deterministic confidence percentage")
    primary_reasoning: str = Field(..., description="Natural language explanation of strategy selection")
    actions: List[RecoveryAction] = Field(..., description="Sequence of recovery actions to run")
    expected_metrics: ExpectedMetrics = Field(..., description="Predicted metrics from the selected strategy")
    is_mock_response: bool = Field(False, description="False for the local rule-based recovery engine")
    planner_metadata: Optional[PlannerMetadata] = Field(None, description="Non-sensitive planner execution metadata")
    alternative_strategies: List[StrategyAlternative] = Field(default_factory=list)
    risk_factors: List[str] = Field(default_factory=list)
    assumptions: List[str] = Field(default_factory=list)
    uncertainties: List[str] = Field(default_factory=list)
    recovery_timeline_minutes: List[int] = Field(default_factory=list)

class PlannerRequest(BaseModel):
    disruption: Disruption = Field(..., description="Active failure or block event context")
    trains: List[TrainState] = Field(..., description="Current snapshots of all trains")
    stations: List[StationState] = Field(..., description="Current snapshots of all stations")

class ValidationFinding(BaseModel):
    code: str
    severity: str
    message: str

class ValidationResult(BaseModel):
    is_valid: bool
    validated_strategy: str
    findings: List[ValidationFinding]
    scenario: Optional[ScenarioOption] = None

class ValidationRequest(BaseModel):
    plan: RecoveryPlan
    monte_carlo_runs: int = Field(3, ge=1, le=10)

class ExplainabilityResponse(BaseModel):
    strategy: str
    rationale: str
    tradeoffs: List[str]
    fallback: str
    validation_summary: str

class WhyNotRequest(BaseModel):
    strategy: str

class WhyNotResponse(BaseModel):
    strategy: str
    reason: str

class ConfidenceResponse(BaseModel):
    strategy: str
    score: float
    factors: List[str]

class PlanRecord(BaseModel):
    id: str
    plan: RecoveryPlan
    status: Literal["proposed", "validated", "rejected", "approved", "committed", "rolled_back"] = "proposed"
    validation: Optional[ValidationResult] = None
    rollback_snapshot: Optional[Dict[str, Any]] = None

class PlanApprovalRequest(BaseModel):
    plan_id: str




