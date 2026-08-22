# NEXUS AI — Deterministic Constraint Specification (v1.0)

## 1. Safety Philosophy: Inviolable Determinism

In safety-critical railway dispatch, **machine learning models must NEVER possess unconstrained write access or final execution authority**. 

NEXUS AI enforces a two-tier constraint architecture:
1. **Tier 1: Hard Deterministic Safety Invariants ($\mathcal{C}_{\text{safety}} \in \{0, 1\}$)**:
   * Non-negotiable physical laws and signalling interlocking rules.
   * If an ML recommendation violates any Tier 1 invariant, the recommendation is **immediately rejected** ($0.00\%$ tolerance) and the system reverts to an exact optimization fallback.
2. **Tier 2: Soft Operational Constraints ($\mathcal{C}_{\text{operational}} \in \mathbb{R}^{\ge 0}$)**:
   * Timetable punctuality targets, passenger transfer connections, traction energy consumption, and crew shift limits.
   * Optimized as penalty terms inside the multi-objective cost function $\mathcal{J}$.

```
                 [ Candidate Action from NEXUS-265M ]
                                  │
                                  ▼
                 ┌──────────────────────────────────┐
                 │    TIER 1: HARD SAFETY ENGINE    │
                 │  • Minimum Headway Violation?    │
                 │  • Block Section Double-Booking? │
                 │  • Interlocking Route Conflict?  │
                 │  • Platform Length Overrun?      │
                 │  • Speed Limit Exceeded?         │
                 └────────────────┬─────────────────┘
                                  │
                     ┌────────────┴────────────┐
                     ▼                         ▼
                 [ PASS ]                  [ FAIL ]
                     │                         │
                     ▼                         ▼
         ┌───────────────────────┐ ┌───────────────────────┐
         │ TIER 2: SOFT COST     │ │ REJECT RECOMMENDATION │
         │ Evaluation in J(s, a) │ │ Trigger CP-SAT Solver │
         └───────────────────────┘ └───────────────────────┘
```

---

## 2. Tier 1: Hard Safety Invariants (Mathematical Formulations)

### 2.1 Spatial & Temporal Headway Invariant ($C_{\text{headway}}$)
For any two consecutive trains $i$ (leader) and $j$ (follower) operating on the same track section $k$:

$$t_{\text{entry}}(j, k) - t_{\text{entry}}(i, k) \ge H_{\text{min}}(k)$$

$$\text{distance}(i, j) \ge d_{\text{brake}}(v_j) + d_{\text{margin}}$$

where $d_{\text{brake}}(v) = \frac{v^2}{2 \cdot a_{\text{service\_brake}}}$ and $H_{\text{min}}(k)$ is the mandatory block headway (typically $120\text{ to }180\text{ seconds}$).

### 2.2 Single Block Section Occupancy Invariant ($C_{\text{block}}$)
Under absolute block signaling, a block section $k \in \mathcal{V}_{\text{sec}}$ can host at most one train simultaneously:

$$\sum_{i \in \mathcal{V}_{\text{trn}}} \mathbb{I}\left( \text{position}(i, t) \in \text{Span}(k) \right) \le 1 \quad \forall k \in \mathcal{V}_{\text{sec}}, \forall t$$

### 2.3 Route & Interlocking Exclusivity Invariant ($C_{\text{route}}$)
If Train $i$ is granted Route $R_1$ and Train $j$ is granted Route $R_2$, the sets of physical switch points and fouling zones must be disjoint:

$$\text{FoulingZones}(R_1) \cap \text{FoulingZones}(R_2) = \emptyset \quad \forall (i, j), i \ne j$$

### 2.4 Platform Berth Capacity Invariant ($C_{\text{platform}}$)
A train $i$ may only berth at platform $p \in \mathcal{V}_{\text{plt}}$ if the platform is unoccupied and physically accommodates the train length:

$$\text{Length}(i) \le \text{BerthLength}(p) \quad \text{and} \quad \text{Occupied}(p, t) = 0$$

### 2.5 Strict Monotonic Temporal Sequencing ($C_{\text{temporal}}$)
For every train $i$ and every station $s$ along its route:

$$t_{\text{actual\_arrival}}(i, s) < t_{\text{actual\_departure}}(i, s)$$

$$t_{\text{actual\_departure}}(i, s) - t_{\text{actual\_arrival}}(i, s) \ge d_{\text{min\_dwell}}(s)$$

$$t_{\text{actual\_arrival}}(i, s+1) \ge t_{\text{actual\_departure}}(i, s) + \text{MinRunTime}(s \to s+1)$$

### 2.6 Maximum Permissible Speed ($C_{\text{speed}}$)
$$v_i(t) \le \min\left( \text{MPS}(k), \text{TSR}(k, t), \text{LocoMaxSpeed}(i) \right)$$
where $\text{MPS}$ is Maximum Permitted Speed and $\text{TSR}$ is Temporary Speed Restriction (Caution Order).

---

## 3. Tier 2: Soft Operational Constraints

| Constraint Name | Mathematical Definition | Penalty Coefficient in $\mathcal{J}$ |
| :--- | :--- | :--- |
| **Timetable Punctuality** | $\sum_i \max(0, t_{\text{arr}}(i, s) - t^{\text{sched}}_{\text{arr}}(i, s))$ | $w_1 = 1.0 \times \text{Priority}(i)$ |
| **Dwell Time Violation** | $\sum_i \max(0, d_{\text{min\_dwell}} - (t_{\text{dep}} - t_{\text{arr}}))$ | $w_2 = 5.0$ |
| **Crew Shift Limit (10h)** | $\mathbb{I}(\text{CrewDutyHours} > 10.0\text{ h}) \cdot 500.0$ | $w_3 = 10.0$ |
| **Passenger Missed Connections**| $\sum_{\text{transfers}} \mathbb{I}(t_{\text{arr}}(\text{Feeder}) > t_{\text{dep}}(\text{Connecting}) - 5\text{m}) \cdot \text{Pax}$ | $w_4 = 2.5$ |
| **Platform Reassignment Penalty**| $\mathbb{I}(\text{AssignedPlatform} \ne \text{ScheduledPlatform}) \cdot 50.0$ | $w_5 = 0.5$ |

---

## 4. Deterministic Validator Algorithm (C++ / Python)

The deterministic validator function $\text{ValidateAction}(\mathcal{S}_t, a)$ executes in $<1.0\text{ms}$:

```python
class DeterministicSafetyValidator:
    def __init__(self, topology: RailTopology):
        self.topology = topology

    def evaluate_safety(self, state: RailwayState, action: Action) -> Tuple[bool, List[str]]:
        violations = []
        
        # 1. Evaluate temporal feasibility
        if not self._check_temporal_ordering(state, action):
            violations.append("TEMPORAL_SEQUENCING_VIOLATION")
            
        # 2. Evaluate headway & block occupancy
        if not self._check_block_occupancy(state, action):
            violations.append("BLOCK_DOUBLE_BOOKING_VIOLATION")
            
        # 3. Evaluate interlocking route exclusivity
        if not self._check_route_interlocking(state, action):
            violations.append("INTERLOCKING_FOULING_CONFLICT")
            
        # 4. Evaluate platform berthing constraints
        if not self._check_platform_clearance(state, action):
            violations.append("PLATFORM_CAPACITY_OR_OCCUPANCY_VIOLATION")
            
        # 5. Evaluate speed / traction compatibility
        if not self._check_traction_speed(state, action):
            violations.append("TRACTION_OR_SPEED_VIOLATION")
            
        is_valid = (len(violations) == 0)
        return is_valid, violations
```
