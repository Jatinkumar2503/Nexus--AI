from pydantic import BaseModel, Field
from typing import List, Optional, Dict

class Disruption(BaseModel):
    id: str = Field(..., description="Unique identifier for the disruption event")
    node_id: str = Field(..., description="The station or junction node ID where the failure occurs")
    duration: int = Field(..., description="Duration of the disruption in minutes")
    severity: str = Field(..., description="Severity class: LOW, MEDIUM, HIGH, CRITICAL")
    description: Optional[str] = Field(None, description="Detailed explanation of the failure")
    start_time: int = Field(0, description="Start time of disruption in minutes from simulation start")

class TrainState(BaseModel):
    train_id: str
    route_name: str
    current_node: str
    next_node: str
    speed_kmh: float
    delay_minutes: float
    passenger_count: int
    coordinates: List[float] = Field(..., description="[Latitude, Longitude] representing spatial coordinates")
    status: str = Field("RUNNING", description="RUNNING, STOPPED, DELAYED, CANCELLED")

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
    explainer: str

class SimulationMetrics(BaseModel):
    total_passenger_delay_minutes: float
    total_energy_kwh: float
    crew_violation_count: int
    resilience_score: float

class SimulationStepResponse(BaseModel):
    simulation_time: int
    trains: List[TrainState]
    stations: List[StationState]
    active_disruptions: List[Disruption]
    metrics: SimulationMetrics
