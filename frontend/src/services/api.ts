// API Service client for connecting the React frontend to the FastAPI backend

const BASE_URL = 'http://127.0.0.1:8000';

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

export const api = {
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
      headers: { 'Content-Type': 'application/json' },
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
      headers: { 'Content-Type': 'application/json' },
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
  }
};
