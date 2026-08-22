# NEXUS AI — Railway Knowledge Graph Specification (v1.0)

## 1. Overview & Heterogeneous Topology

The NEXUS Railway Knowledge Graph represents static infrastructure, dynamic rolling stock, spatial occupancy, and operational constraints as a typed heterogeneous multigraph $\mathcal{G}_t = (\mathcal{V}, \mathcal{E}, \mathcal{X}_t)$.

```
   (Platform) ──[IN_STATION]──► (Station) ◄──[CONNECTS_TO]──► (Block Section)
       ▲                            ▲                               ▲
       │ [OCCUPIES_PLT]             │ [APPROACHES]                  │ [OCCUPIES_SEC]
       │                            │                               │
       └──────────────────────── (Train) ───────────────────────────┘
                                   │   ▲
                     [PRECEDES]    │   │  [CONFLICTS_WITH]
                                   ▼   │
                                (Train)
```

---

## 2. Node Schema & Feature Tensor Definitions

### 2.1 Station & Junction Nodes ($\mathcal{V}_{\text{stn}}$)
Represents physical railway stations, major junctions, bypass yards, and terminal throats.

| Feature Index | Feature Name | Type | Range / Dimension | Description |
| :--- | :--- | :--- | :--- | :--- |
| 0 | `station_id_emb` | Categorical Embedding | $\mathbb{R}^{64}$ | Learnable unique entity embedding |
| 1 | `latitude_norm` | Continuous (Normalized) | $[0.0, 1.0]$ | Min-max scaled latitude coordinate |
| 2 | `longitude_norm` | Continuous (Normalized) | $[0.0, 1.0]$ | Min-max scaled longitude coordinate |
| 3 | `platform_count` | Integer (Scaled) | $[1, 24] \to [0.0, 1.0]$ | Total functional platforms |
| 4 | `is_junction` | Binary | $\{0, 1\}$ | Flag for $\ge 3$ intersecting corridors |
| 5 | `is_terminal` | Binary | $\{0, 1\}$ | Flag for dead-end terminal stations |
| 6 | `base_dwell_min` | Continuous | $[1.0, 30.0]$ | Scheduled minimum passenger dwell time |
| 7 | `active_train_count`| Integer (Scaled) | $[0, 30]$ | Real-time trains currently in station yard |
| 8 | `available_platforms`| Integer (Scaled) | $[0, 24]$ | Real-time unoccupied platforms |
| 9 | `yard_congestion_ratio`| Continuous | $[0.0, 1.0]$ | $\frac{\text{Occupied Platforms}}{\text{Total Platforms}}$ |

### 2.2 Block Section Nodes ($\mathcal{V}_{\text{sec}}$)
Represents directional track segments between consecutive signals or block stations.

| Feature Index | Feature Name | Type | Range / Dimension | Description |
| :--- | :--- | :--- | :--- | :--- |
| 0 | `section_id_emb` | Categorical Embedding | $\mathbb{R}^{64}$ | Learnable segment identifier |
| 1 | `length_km` | Continuous | $[0.5, 25.0]\text{ km}$ | Physical length of block section |
| 2 | `max_permitted_speed`| Continuous (Normalized)| $[30, 200]\text{ km/h}$ | Maximum sectional speed (MPS) |
| 3 | `gradient_permille` | Continuous | $[-25.0, +25.0]$ | Track incline/decline gradient |
| 4 | `is_electrified` | Binary | $\{0, 1\}$ | 25kV AC overhead electrification flag |
| 5 | `signal_aspect` | Categorical (One-Hot) | $\mathbb{R}^4$ | [Red, Single Yellow, Double Yellow, Green] |
| 6 | `active_occupancy` | Integer | $\{0, 1\}$ | Absolute block occupancy (1 = occupied) |
| 7 | `temporary_speed_res`| Continuous | $[0, 130]\text{ km/h}$ | Active Caution Order speed limit |
| 8 | `direction_outbound`| Binary | $\{0, 1\}$ | Track directionality indicator |

### 2.3 Train Entity Nodes ($\mathcal{V}_{\text{trn}}$)
Represents active train rakes operating within the digital twin.

| Feature Index | Feature Name | Type | Range / Dimension | Description |
| :--- | :--- | :--- | :--- | :--- |
| 0 | `train_number_emb` | Categorical Embedding | $\mathbb{R}^{64}$ | Learnable train schedule entity embedding |
| 1 | `priority_weight` | Continuous | $[1.0, 5.0]$ | Dispatch precedence multiplier |
| 2 | `train_category` | Categorical (One-Hot) | $\mathbb{R}^6$ | [Vande Bharat, Rajdhani/Shatabdi, Mail/Exp, Passenger, Freight, Special] |
| 3 | `length_meters` | Continuous | $[150, 750]\text{ m}$ | Physical rake length (coaches/wagons) |
| 4 | `trailing_tonnage` | Continuous | $[400, 6000]\text{ t}$ | Gross trailing load |
| 5 | `current_speed_kmh` | Continuous | $[0.0, 160.0]$ | Real-time GPS/telemetry speed |
| 6 | `cumulative_delay_min`| Continuous | $[-30.0, 360.0]$ | Current punctuality deviation ($t_{\text{act}} - t_{\text{sched}}$) |
| 7 | `passenger_pax_count`| Continuous (Scaled) | $[0, 2500]$ | Real-time onboard passenger volume |
| 8 | `remaining_distance_km`| Continuous | $[0, 2000]\text{ km}$ | Distance to final destination |
| 9 | `crew_duty_hours_left`| Continuous | $[0.0, 10.0]\text{ h}$ | Remaining crew allowable driving shift |
| 10 | `traction_type` | Categorical (One-Hot) | $\mathbb{R}^3$ | [Electric EMU, Electric Loco, Diesel Loco] |

### 2.4 Platform Nodes ($\mathcal{V}_{\text{plt}}$)
Represents discrete berthing tracks within station perimeters.

| Feature Index | Feature Name | Type | Range / Dimension | Description |
| :--- | :--- | :--- | :--- | :--- |
| 0 | `platform_id_emb` | Categorical Embedding | $\mathbb{R}^{32}$ | Platform identifier |
| 1 | `berth_length_m` | Continuous | $[200, 700]\text{ m}$ | Maximum allowable rake length |
| 2 | `is_occupied` | Binary | $\{0, 1\}$ | Real-time track circuit status |
| 3 | `is_electrified` | Binary | $\{0, 1\}$ | Overhead catenary presence |
| 4 | `time_until_free_min`| Continuous | $[0.0, 120.0]$ | Estimated time until current occupant clears |

---

## 3. Relational Edge Schema & Semantics

| Edge Type | Source Node | Target Node | Edge Attributes | Description |
| :--- | :--- | :--- | :--- | :--- |
| `CONNECTS_TO` | $\mathcal{V}_{\text{stn}}$ / $\mathcal{V}_{\text{sec}}$ | $\mathcal{V}_{\text{sec}}$ / $\mathcal{V}_{\text{stn}}$ | `[distance_km, max_speed, switch_time_min]` | Physical track connectivity |
| `IN_STATION` | $\mathcal{V}_{\text{plt}}$ | $\mathcal{V}_{\text{stn}}$ | `[platform_num, is_mainline]` | Station containment hierarchy |
| `OCCUPIES_SEC` | $\mathcal{V}_{\text{trn}}$ | $\mathcal{V}_{\text{sec}}$ | `[entry_time, headway_distance_m]` | Train currently physically inside section |
| `OCCUPIES_PLT` | $\mathcal{V}_{\text{trn}}$ | $\mathcal{V}_{\text{plt}}$ | `[berth_time, expected_departure]` | Train currently berthed at platform |
| `ROUTES_THROUGH`| $\mathcal{V}_{\text{trn}}$ | $\mathcal{V}_{\text{stn}}$ | `[sched_arr, sched_dep, sched_dwell, is_stop]` | Scheduled itinerary sequence |
| `PRECEDES` | $\mathcal{V}_{\text{trn}}$ | $\mathcal{V}_{\text{trn}}$ | `[headway_gap_seconds, spatial_gap_km]` | Direct leading/following relationship |
| `CONFLICTS_WITH`| $\mathcal{V}_{\text{trn}}$ | $\mathcal{V}_{\text{trn}}$ | `[conflict_type, time_to_conflict_min]` | Imminent routing or crossing collision hazard |

---

## 4. PyTorch Geometric HeteroData Specification

In the PyTorch training pipeline, batch graph instances are formatted as `torch_geometric.data.HeteroData`:

```python
from torch_geometric.data import HeteroData
import torch

data = HeteroData()

# Node feature tensors
data['station'].x = torch.zeros((N_stn, 10), dtype=torch.float32)
data['section'].x = torch.zeros((N_sec, 9), dtype=torch.float32)
data['train'].x   = torch.zeros((N_trn, 11), dtype=torch.float32)
data['platform'].x = torch.zeros((N_plt, 5), dtype=torch.float32)

# Graph Adjacency edge_index tensors
data['station', 'connects_to', 'section'].edge_index = torch.zeros((2, E_conn), dtype=torch.long)
data['section', 'connects_to', 'station'].edge_index = torch.zeros((2, E_conn), dtype=torch.long)
data['train', 'occupies', 'section'].edge_index       = torch.zeros((2, E_occ_sec), dtype=torch.long)
data['train', 'occupies', 'platform'].edge_index      = torch.zeros((2, E_occ_plt), dtype=torch.long)
data['train', 'routes_through', 'station'].edge_index = torch.zeros((2, E_routes), dtype=torch.long)
data['train', 'precedes', 'train'].edge_index         = torch.zeros((2, E_prec), dtype=torch.long)
data['train', 'conflicts_with', 'train'].edge_index   = torch.zeros((2, E_conf), dtype=torch.long)

# Global environment tensor
data.weather = torch.zeros((1, 5), dtype=torch.float32)
```

---

## 5. Topological Graph Invariants

To guarantee scientific consistency during data generation and simulation:
1. **Connectivity Invariant**: The physical infrastructure subgraph $(\mathcal{V}_{\text{stn}} \cup \mathcal{V}_{\text{sec}}, \mathcal{E}_{\text{topo}})$ must be strongly connected across designated mainline corridors.
2. **Single Occupancy Invariant**: For all standard absolute block sections $k \in \mathcal{V}_{\text{sec}}$, $\text{in\_degree}_{\text{occupies}}(k) \le 1$.
3. **Platform Exclusivity Invariant**: For all platform nodes $p \in \mathcal{V}_{\text{plt}}$, $\text{in\_degree}_{\text{occupies}}(p) \le 1$.
4. **Precedence Acyclicity**: The directed graph $(\mathcal{V}_{\text{trn}}, \mathcal{E}_{\text{precede}})$ within any common section $k$ must be a strict directed acyclic graph (DAG).
