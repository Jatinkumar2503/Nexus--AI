// API Service client for connecting the React frontend to the FastAPI backend

const BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '');
let dispatcherToken = '';

export function setDispatcherToken(token: string): void {
  dispatcherToken = token.trim();
}

function mutationHeaders(): HeadersInit {
  return {
    'Content-Type': 'application/json',
    ...(dispatcherToken ? { Authorization: `Bearer ${dispatcherToken}` } : {}),
  };
}

export interface StationNode {
  name: string;
  coords: [number, number]; // [Latitude, Longitude]
  platforms: number;
  base_dwell_time: number;
}

export interface TrackEdge {
  from_node: string;
  to_node: string;
  distance_km: number;
  travel_time_min: number;
  direction: "outbound" | "inbound";
  status: "open" | "blocked";
}

export interface TopologyResponse {
  status: string;
  nodes: { [key: string]: StationNode };
  edges: TrackEdge[];
}

export interface TrainState {
  train_id: string;
  service_type: string;
  direction: string;
  current_node: string;
  next_node: string;
  speed_kmh: number;
  delay_minutes: number;
  passenger_count: number;
  coordinates: [number, number]; // [Latitude, Longitude]
  status: string; // "WAITING", "RUNNING", "DWELLING", "TERMINATED", "DELAYED"
  energy_consumed_kwh: number;
  crew_violated: boolean;
  priority_tokens?: number;
  bids_paid?: number;
  voltage?: number;
  telemetry_packet_lost?: boolean;
}

export interface StationState {
  station_id: string;
  name: string;
  occupied_platforms: string[];
  capacity: number;
  queue: string[];
}

export interface Disruption {
  id: string;
  node_id: string | null;
  edge_id: string | null;
  duration: number;
  severity: string;
  description: string;
  start_time: number;
}

export interface SimulationMetrics {
  total_passenger_delay_minutes: number;
  total_energy_kwh: number;
  crew_violation_count: number;
  resilience_score: number;
}

export interface SimulationStateResponse {
  simulation_time: string;
  trains: TrainState[];
  stations: StationState[];
  active_disruptions: Disruption[];
  metrics: SimulationMetrics;
  negotiation_logs: string[];
}

export interface ScenarioOption {
  id: string;
  name: string;
  description: string;
  delay_minutes: number;
  energy_cost_kwh: number;
  crew_violations_count: number;
  is_legal: boolean;
  resilience_score: number;
  explainer: string;
  is_pareto_optimal: boolean;
}

export interface CompareScenariosResponse {
  status: string;
  scenarios: ScenarioOption[];
}

export interface RecoveryAction {
  train_id: string;
  action_type: 'detour' | 'short_turn' | 'hold' | 'speed_throttle' | 'crew_swap' | 'inspection' | 'reduce_acceleration' | 'priority_dispatch';
  location: string;
  hold_duration_minutes?: number;
  routing_path?: string[];
  rationale?: string;
}

export interface RecoveryPlan {
  recommended_strategy: 'do_nothing' | 'detour' | 'short_turn' | 'hold' | 'reroute' | 'reroute_and_prioritize' | 'crew_swap' | 'inspection' | 'mixed_strategy';
  confidence_score: number;
  primary_reasoning: string;
  actions: RecoveryAction[];
  expected_metrics: {
    delay_minutes: number;
    energy_kwh: number;
    crew_violations: number;
    resilience_score: number;
  };
  planner_metadata?: { mode: 'local' | 'enhanced'; provider: 'local' | 'openai'; model?: string; latency_ms?: number; execution_time_ms: number; tool_calls: number; fallback_reason?: string };
  alternative_strategies?: Array<{ strategy: string; rationale: string; tradeoff: string; rank: number }>;
  risk_factors?: string[];
  assumptions?: string[];
  uncertainties?: string[];
  recovery_timeline_minutes?: number[];
}

export interface ValidationResult {
  is_valid: boolean;
  validated_strategy: string;
  findings: Array<{ code: string; severity: string; message: string }>;
  scenario?: ScenarioOption | null;
}

export interface PlanRecord {
  id: string;
  plan: RecoveryPlan;
  status: 'proposed' | 'validated' | 'rejected' | 'approved' | 'committed';
  validation?: ValidationResult | null;
}

export interface PlannerStatus { mode: 'local' | 'auto' | 'enhanced'; model: string; enhanced_available: boolean; is_mock_response: boolean; }

export const api = {
  async getPlannerStatus(): Promise<PlannerStatus> { const response = await fetch(`${BASE_URL}/api/planner/status`); if (!response.ok) throw new Error('Failed to fetch planner status'); return response.json(); },
  async createLifecyclePlan(request: { disruption: Disruption; trains: TrainState[]; stations: StationState[] }): Promise<PlanRecord> { const response = await fetch(`${BASE_URL}/api/planner/plans`, { method: 'POST', headers: mutationHeaders(), body: JSON.stringify(request) }); if (!response.ok) throw new Error('Failed to create plan'); return response.json(); },
  async validateLifecyclePlan(id: string): Promise<PlanRecord> { const response = await fetch(`${BASE_URL}/api/planner/plans/${id}/validate`, { method: 'POST', headers: dispatcherToken ? { Authorization: `Bearer ${dispatcherToken}` } : undefined }); if (!response.ok) throw new Error('Failed to validate plan'); return response.json(); },
  async approveLifecyclePlan(id: string): Promise<PlanRecord> { const response = await fetch(`${BASE_URL}/api/planner/plans/${id}/approve`, { method: 'POST', headers: dispatcherToken ? { Authorization: `Bearer ${dispatcherToken}` } : undefined }); if (!response.ok) throw new Error('Failed to approve plan'); return response.json(); },
  async commitLifecyclePlan(id: string): Promise<PlanRecord> { const response = await fetch(`${BASE_URL}/api/planner/plans/${id}/commit`, { method: 'POST', headers: dispatcherToken ? { Authorization: `Bearer ${dispatcherToken}` } : undefined }); if (!response.ok) throw new Error('Failed to commit plan'); return response.json(); },
  async getScenarioPresets(): Promise<any> { const response = await fetch(`${BASE_URL}/api/scenarios/presets`); if (!response.ok) throw new Error('Failed to fetch presets'); return response.json(); },
  async getRecoveryMemory(): Promise<any> { const response = await fetch(`${BASE_URL}/api/memory/outcomes`); if (!response.ok) throw new Error('Failed to fetch recovery memory'); return response.json(); },
  async getRecoveryPreferences(): Promise<any> { const response = await fetch(`${BASE_URL}/api/memory/preferences`); if (!response.ok) throw new Error('Failed to fetch preferences'); return response.json(); },
  async setRecoveryPreferences(preferences: Record<string, unknown>): Promise<any> { const response = await fetch(`${BASE_URL}/api/memory/preferences`, { method: 'PUT', headers: mutationHeaders(), body: JSON.stringify({ preferences }) }); if (!response.ok) throw new Error('Failed to save preferences'); return response.json(); },
  async getReplayTimeline(): Promise<any> { const response = await fetch(`${BASE_URL}/api/replay/timeline`); if (!response.ok) throw new Error('Failed to fetch replay timeline'); return response.json(); },
  async injectScenarioPreset(name: string): Promise<any> { const response = await fetch(`${BASE_URL}/api/scenarios/presets/${name}/inject`, { method: 'POST', headers: dispatcherToken ? { Authorization: `Bearer ${dispatcherToken}` } : undefined }); if (!response.ok) throw new Error('Failed to inject preset'); return response.json(); },
  /**
   * Fetch the static rail network topology (station nodes and track edges).
   */
  async getTopology(): Promise<TopologyResponse> {
    const response = await fetch(`${BASE_URL}/api/topology`);
    if (!response.ok) {
      throw new Error(`Failed to fetch topology: ${response.statusText}`);
    }
    return response.json();
  },

  /**
   * Fetch the current position and status of all trains.
   */
  async getLiveTrains(): Promise<{ status: string; simulation_time: string; trains: TrainState[] }> {
    const response = await fetch(`${BASE_URL}/api/live-trains`);
    if (!response.ok) {
      throw new Error(`Failed to fetch live trains: ${response.statusText}`);
    }
    return response.json();
  },

  /**
   * Fetch the full, detailed state of the running simulation.
   */
  async getSimulationState(): Promise<SimulationStateResponse> {
    const response = await fetch(`${BASE_URL}/api/simulation/state`);
    if (!response.ok) {
      throw new Error(`Failed to fetch simulation state: ${response.statusText}`);
    }
    return response.json();
  },

  /**
   * Control the simulation playback clock (play, pause, reset, step).
   */
  async controlSimulation(action: "play" | "pause" | "reset" | "step", speed: number = 30.0): Promise<any> {
    const response = await fetch(`${BASE_URL}/api/simulation/control`, {
      method: 'POST',
      headers: mutationHeaders(),
      body: JSON.stringify({ action, speed })
    });
    if (!response.ok) {
      throw new Error(`Failed to control simulation: ${response.statusText}`);
    }
    return response.json();
  },

  /**
   * Inject a network disruption (block track or station).
   */
  async injectDisruption(nodeId: string | null, edgeId: string | null, duration: number, description: string): Promise<any> {
    const response = await fetch(`${BASE_URL}/api/disruption/inject`, {
      method: 'POST',
      headers: mutationHeaders(),
      body: JSON.stringify({
        node_id: nodeId,
        edge_id: edgeId,
        duration,
        severity: "HIGH",
        description
      })
    });
    if (!response.ok) {
      throw new Error(`Failed to inject disruption: ${response.statusText}`);
    }
    return response.json();
  },

  /**
   * Fetch parallel simulation scenario comparisons.
   */
  async compareScenarios(): Promise<CompareScenariosResponse> {
    const response = await fetch(`${BASE_URL}/api/scenarios/compare`);
    if (!response.ok) {
      throw new Error(`Failed to compare scenarios: ${response.statusText}`);
    }
    return response.json();
  },

  /**
   * Commit a chosen recovery scenario.
   */
  async resolveScenario(strategy: string): Promise<any> {
    const response = await fetch(`${BASE_URL}/api/scenarios/resolve`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ strategy })
    });
    if (!response.ok) {
      throw new Error(`Failed to resolve scenario: ${response.statusText}`);
    }
    return response.json();
  },

  async approveScenario(strategy: string): Promise<any> {
    const response = await fetch(`${BASE_URL}/api/scenarios/approve`, {
      method: 'POST', headers: mutationHeaders(), body: JSON.stringify({ strategy })
    });
    if (!response.ok) throw new Error(`Failed to approve scenario: ${response.statusText}`);
    return response.json();
  },

  async getScenarioExplanation(strategy: string): Promise<any> {
    const response = await fetch(`${BASE_URL}/api/scenarios/${strategy}/explain`);
    if (!response.ok) throw new Error(`Failed to explain scenario: ${response.statusText}`);
    return response.json();
  },

  async getScenarioConfidence(strategy: string): Promise<any> {
    const response = await fetch(`${BASE_URL}/api/scenarios/${strategy}/confidence`);
    if (!response.ok) throw new Error(`Failed to fetch confidence: ${response.statusText}`);
    return response.json();
  },

  async whyNotScenario(strategy: string): Promise<any> {
    const response = await fetch(`${BASE_URL}/api/scenarios/why-not`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ strategy })
    });
    if (!response.ok) throw new Error(`Failed to explain rejection: ${response.statusText}`);
    return response.json();
  },

  subscribePlannerEvents(onEvent: (event: { stage: string; message: string }) => void): EventSource {
    const source = new EventSource(`${BASE_URL}/api/planner/events`);
    source.addEventListener('execution', (event) => onEvent(JSON.parse(event.data)));
    return source;
  },

  /**
   * Execute real-time inference on the trained NEXUS foundation model.
   */
  async nexusNeuralInfer(payload: {
    train_id: string;
    location_station: string;
    current_delay_min: number;
    weather?: string;
    train_priority?: number;
    platform_count?: number;
    section_mps?: number;
    hour_of_day?: number;
  }): Promise<{
    status: string;
    is_safety_approved: boolean;
    safety_violations: string[];
    recommended_action: string;
    confidence_pct: number;
    predictions: {
      delay_15m_median: number;
      delay_15m_90pct_interval: [number, number];
      uncertainty_spread_minutes: number;
      congestion_level: string;
      conflict_hazard_probability: number;
    };
    causal_explanation: {
      summary: string;
      reasons: string[];
      expected_impact: string;
    };
    performance: {
      inference_latency_ms: number;
      model_parameters: number;
      device: string;
    };
  }> {
    const response = await fetch(`${BASE_URL}/api/nexus/infer`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    if (!response.ok) {
      throw new Error(`Failed to execute neural inference: ${response.statusText}`);
    }
    return response.json();
  },

  /**
   * Retrieve scientific benchmark comparisons of NEXUS against baselines and CP-SAT.
   */
  async getNexusBenchmarks(): Promise<any> {
    const response = await fetch(`${BASE_URL}/api/nexus/benchmarks`);
    if (!response.ok) {
      throw new Error(`Failed to fetch benchmarks: ${response.statusText}`);
    }
    return response.json();
  }
};

export const apiService = api;
