# NEXUS AI — Research Specification & Mathematical Formulation (v1.0)

## 1. Executive Summary & North-Star Objective

NEXUS AI is a spatiotemporal railway intelligence and decision-support system designed to model railway network dynamics, predict multi-horizon delay propagation and structural conflicts, evaluate candidate operational interventions, and approximate exact optimization decisions while strictly adhering to deterministic safety constraints.

The core research question investigated:
$$\text{"Can a learned heterogeneous spatiotemporal model approximate exact combinatorial dispatch decisions }$$
$$\text{with } <50\text{ms inference latency while guaranteeing } 0.00\% \text{ safety constraint violations?"}$$

---

## 2. Mathematical Notation & Problem Formulation

Let the continuous time domain be discretized into uniform time steps $t \in \{0, 1, \dots, T\}$ with step size $\Delta t$ (default $\Delta t = 60\text{ seconds}$).

### 2.1 Dynamic Heterogeneous Railway Graph

We represent the railway network as a dynamic heterogeneous graph:

$$\mathcal{G}_t = (\mathcal{V}, \mathcal{E}, \mathcal{X}_t, \mathcal{W}_t)$$

where:
* $\mathcal{V} = \mathcal{V}_{\text{stn}} \cup \mathcal{V}_{\text{sec}} \cup \mathcal{V}_{\text{trn}} \cup \mathcal{V}_{\text{plt}}$ is the set of heterogeneous nodes.
  * $\mathcal{V}_{\text{stn}}$: Stations and Junctions ($N_{\text{stn}}$ nodes).
  * $\mathcal{V}_{\text{sec}}$: Directional Block Sections ($N_{\text{sec}}$ nodes).
  * $\mathcal{V}_{\text{trn}}$: Active Trains in the network at time $t$ ($N_{\text{trn}}(t)$ nodes).
  * $\mathcal{V}_{\text{plt}}$: Station Platforms ($N_{\text{plt}}$ nodes).
* $\mathcal{E} = \mathcal{E}_{\text{topo}} \cup \mathcal{E}_{\text{occupy}} \cup \mathcal{E}_{\text{route}} \cup \mathcal{E}_{\text{precede}} \cup \mathcal{E}_{\text{conflict}}$ is the set of typed directed edges.
* $\mathcal{X}_t = \{\mathbf{x}_v(t) \mid v \in \mathcal{V}\}$ is the time-varying node feature tensor.
* $\mathcal{W}_t$ is the environmental and exogenous context vector (weather, traction power grid status, demand shocks).

```
                      [ Dynamic Graph G_t ]
                                │
    ┌──────────────┬────────────┴────────────┬──────────────┐
    ▼              ▼                         ▼              ▼
 Station        Section                    Train         Platform
  Nodes          Nodes                     Nodes          Nodes
 (V_stn)        (V_sec)                   (V_trn)        (V_plt)
    │              │                         │              │
    └──────┬───────┴────────────┬────────────┴──────┬───────┘
           │                    │                   │
           ▼                    ▼                   ▼
    Physical Edges       Occupancy Edges     Precedence Edges
     (E_topo)              (E_occupy)          (E_precede)
```

---

## 3. Operational State Vector

At any dispatch epoch $t$, the full system state $\mathcal{S}_t$ is defined as:

$$\mathcal{S}_t = \left( \mathcal{G}_t, \mathcal{X}_t, \mathcal{T}_t, \mathcal{D}_t, \mathcal{W}_t, \mathcal{R}_t \right)$$

where:
1. $\mathcal{G}_t, \mathcal{X}_t$: The instantaneous graph topology and node states.
2. $\mathcal{T}_t$: The static and active timetables:
   $$\mathcal{T}_t = \left\{ (i, s, t^{\text{sched}}_{\text{arr}}(i, s), t^{\text{sched}}_{\text{dep}}(i, s), d^{\text{base}}_{\text{dwell}}(i, s)) \mid i \in \mathcal{V}_{\text{trn}}, s \in \text{Route}(i) \right\}$$
3. $\mathcal{D}_t$: Real-time passenger/freight demand profiles and priority matrices.
4. $\mathcal{W}_t$: Environmental telemetry:
   $$\mathbf{w}_t = [\text{temperature}, \text{rainfall\_mm}, \text{visibility\_m}, \text{wind\_speed\_kmh}, \text{is\_extreme\_weather}]$$
5. $\mathcal{R}_t$: Active and predicted disruption events:
   $$\mathcal{R}_t = \left\{ (r_k, \text{type}_k, \text{loc}_k, t^{\text{start}}_k, t^{\text{end}}_k, \text{severity}_k) \right\}$$

---

## 4. Multi-Objective Cost Function

Given a lookahead horizon $H$ (e.g., $H = 120\text{ minutes}$), the cumulative operational cost $\mathcal{J}(\mathcal{S}_t, \mathbf{A}_{t:t+H})$ for an action trajectory $\mathbf{A}_{t:t+H} = (\mathcal{A}_t, \mathcal{A}_{t+1}, \dots, \mathcal{A}_{t+H})$ is defined as:

$$\min_{\mathbf{A}_{t:t+H}} \mathcal{J} = \sum_{\tau=t}^{t+H} \gamma^{\tau-t} \left[ w_1 D(\tau) + w_2 C(\tau) + w_3 G(\tau) + w_4 P(\tau) + w_5 O(\tau) \right]$$

where $\gamma \in (0, 1]$ is the temporal discount factor, and the component cost terms are:

### 4.1 Weighted Train Delay ($D(\tau)$)
$$D(\tau) = \sum_{i \in \mathcal{V}_{\text{trn}}(\tau)} p_i \cdot \max\left(0, t^{\text{actual}}_{\text{arr}}(i, \tau) - t^{\text{sched}}_{\text{arr}}(i, \tau)\right)$$
where $p_i \ge 1.0$ is the train priority coefficient (e.g., Vande Bharat = 5.0, Rajdhani = 4.0, Superfast Express = 3.0, Freight Container = 1.5, Empty Rake = 1.0).

### 4.2 Conflict Hazard Penalty ($C(\tau)$)
$$C(\tau) = \sum_{(i, j) \in \text{Pairs}(\mathcal{V}_{\text{trn}})} \mathbb{I}\left( \text{distance}(i, j) < \text{BrakingDistance}(v_i) + \delta_{\text{buffer}} \right)$$

### 4.3 Section Congestion & Saturation ($G(\tau)$)
$$G(\tau) = \sum_{k \in \mathcal{V}_{\text{sec}}} \left( \frac{\text{ActiveTrains}(k, \tau)}{\text{Capacity}(k)} \right)^2$$

### 4.4 Passenger Disruption Impact ($P(\tau)$)
$$P(\tau) = \sum_{i \in \mathcal{V}_{\text{trn}}(\tau)} \text{PaxCount}(i) \cdot \text{Delay}_i(\tau)$$

### 4.5 Dispatch Operational Cost ($O(\tau)$)
$$O(\tau) = \sum_{a \in \mathcal{A}_\tau} \text{Cost}(a)$$
(Penalizes excessive platform reassignments, unnecessary detours, or unwarranted speed throttling).

---

## 5. Hard Safety Invariants

Unlike heuristic dispatchers that treat safety violations as penalty terms in $\mathcal{J}$, **NEXUS AI defines safety as an inviolable hard barrier**:

$$\mathcal{C}_{\text{safety}}(\mathcal{S}_\tau, \mathcal{A}_\tau) = 1 \quad \forall \tau \in [t, t+H]$$

Any candidate action $\mathcal{A}_\tau$ yielding $\mathcal{C}_{\text{safety}} = 0$ is strictly prohibited and immediately triggers fallback resolution.

---

## 6. Learning Tasks & Mathematical Losses

The NEXUS-265M model is formulated as a multi-task spatiotemporal network $\mathcal{M}_\theta(\mathcal{S}_t)$ producing representations for five simultaneous tasks:

```
                          [ NEXUS Backbone Representation ]
                                          │
       ┌──────────────┬───────────────────┼───────────────────┬──────────────┐
       ▼              ▼                   ▼                   ▼              ▼
  Task 1: Delay  Task 2: Congestion  Task 3: Conflict  Task 4: State    Task 5: Action
   Quantiles        Classes            Focal Prob        Evolution         Ranking
```

### Task 1: Multi-Horizon Quantile Delay Prediction
Predicts delays for horizons $h \in \{15\text{m}, 30\text{m}, 60\text{m}, 120\text{m}\}$ at quantiles $q \in \{0.1, 0.5, 0.9\}$ using Pinball Loss:

$$\mathcal{L}_{\text{delay}} = \sum_{h} \sum_{q} \max\left( q(y_h - \hat{y}_{h,q}), (q - 1)(y_h - \hat{y}_{h,q}) \right)$$

### Task 2: Section Congestion Classification
Predicts congestion level $\hat{\mathbf{g}}_k \in \{\text{LOW}, \text{MEDIUM}, \text{HIGH}, \text{CRITICAL}\}$ using Cross-Entropy Loss:

$$\mathcal{L}_{\text{cong}} = -\sum_{k \in \mathcal{V}_{\text{sec}}} \sum_{c=1}^4 g_{k,c} \log \hat{g}_{k,c}$$

### Task 3: Rare Conflict Hazard Prediction
Predicts pairwise conflict probability $\hat{p}_{ij}$ using Focal Loss ($\alpha=0.25, \gamma=2.0$) to counteract severe class imbalance ($<0.5\%$ positive):

$$\mathcal{L}_{\text{conf}} = -\sum_{(i,j)} \left[ \alpha (1 - \hat{p}_{ij})^\gamma y_{ij} \log \hat{p}_{ij} + (1 - \alpha) \hat{p}_{ij}^\gamma (1 - y_{ij}) \log(1 - \hat{p}_{ij}) \right]$$

### Task 4: Future State Representation Evolution
Self-supervised predictive coding aligning future graph state representations:

$$\mathcal{L}_{\text{state}} = \left\| \mathbf{z}_{\mathcal{G}_{t+H}} - \hat{\mathbf{z}}_{\mathcal{G}_{t+H}} \right\|_2^2$$

### Task 5: Optimization Oracle Policy Ranking
Supervised imitation of the CP-SAT optimization oracle over $K$ candidate actions using ListNet listwise ranking loss:

$$\mathcal{L}_{\text{policy}} = -\sum_{k=1}^K P(a_k \mid \mathcal{S}_t) \log \hat{P}(a_k \mid \mathcal{S}_t)$$
where $P(a_k \mid \mathcal{S}_t) = \frac{\exp(-\mathcal{J}(a_k)/\tau_{\text{temp}})}{\sum_j \exp(-\mathcal{J}(a_j)/\tau_{\text{temp}})}$.

---

## 7. Joint Training Objective

$$\mathcal{L}_{\text{total}} = \lambda_1 \mathcal{L}_{\text{delay}} + \lambda_2 \mathcal{L}_{\text{cong}} + \lambda_3 \mathcal{L}_{\text{conf}} + \lambda_4 \mathcal{L}_{\text{state}} + \lambda_5 \mathcal{L}_{\text{policy}}$$

| Parameter | Default Weight | Description |
| :--- | :--- | :--- |
| $\lambda_1$ | $1.0$ | Multi-horizon quantile delay loss |
| $\lambda_2$ | $0.5$ | Section congestion classification loss |
| $\lambda_3$ | $2.0$ | Focal conflict hazard loss (high weight due to rarity) |
| $\lambda_4$ | $0.2$ | Self-supervised latent state dynamics loss |
| $\lambda_5$ | $1.5$ | Policy action ranking loss from CP-SAT oracle |
