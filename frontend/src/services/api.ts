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
  status: string; // "WAITING", "RUNNING", "DWELLING", "TERMINATED"
}

export interface LiveTrainsResponse {
  status: string;
  simulation_time: string;
  trains: TrainState[];
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
  async getLiveTrains(): Promise<LiveTrainsResponse> {
    const response = await fetch(`${BASE_URL}/api/live-trains`);
    if (!response.ok) {
      throw new Error(`Failed to fetch live trains: ${response.statusText}`);
    }
    return response.json();
  },

  /**
   * Fetch the detailed system health status.
   */
  async getHealth(): Promise<{ status: string; components: Record<string, string> }> {
    const response = await fetch(`${BASE_URL}/api/health`);
    if (!response.ok) {
      throw new Error(`Failed to fetch health check: ${response.statusText}`);
    }
    return response.json();
  }
};
