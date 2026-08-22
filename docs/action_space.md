# NEXUS AI — Operational Action Space & Counterfactual Branching (v1.0)

## 1. Overview & Action Philosophy

In NEXUS AI, the model does **not** generate unconstrained continuous control signals (such as raw accelerator voltages or random track switches). Instead, dispatch recommendations are selected from an **operationally certified discrete action space** $\mathcal{A}(\mathcal{S}_t)$ corresponding to real Indian Railways Section Controller commands.

```
                         [ Current Railway State S_t ]
                                       │
                ┌──────────────────────┴──────────────────────┐
                ▼                                             ▼
     [ Station Level Actions ]                     [ Section Level Actions ]
     • HOLD_AT_STATION                             • SECTION_ENTRY_HOLD
     • ALTER_DWELL_TIME                            • CHANGE_PRECEDENCE (Overtake)
     • CHANGE_PLATFORM                             • SPEED_THROTTLE (Caution)
     • CANCEL_HALT                                 • REROUTE_VIA_DETOUR
```

---

## 2. Action Taxonomy & Parameterization

Every action $a \in \mathcal{A}(\mathcal{S}_t)$ is parameterized as a structured tuple:

$$a = (\text{ActionType}, \text{TargetTrainID}, \text{TargetLocationID}, \mathbf{\theta}_{\text{params}})$$

| Action Type | Parameters ($\mathbf{\theta}$) | Operational Description | Valid Preconditions |
| :--- | :--- | :--- | :--- |
| `HOLD_AT_STATION` | `duration_min` $\in [1, 30]$ | Hold train at station platform/loop line | Train is berthed or approaching station |
| `RELEASE_TRAIN` | `dispatch_priority` $\in [1, 5]$ | Clear signal and dispatch train immediately | Outbound block section is unoccupied |
| `CHANGE_PLATFORM` | `new_platform_id` $\in \mathcal{V}_{\text{plt}}$ | Divert train to alternative platform track | Alternative platform is free and route unlocked |
| `CHANGE_PRECEDENCE` | `overtaking_train_id`, `loop_stn` | Divert lower-priority train to loop line to allow trailing express train to overtake | Station has available loop line; follower has higher priority |
| `ALTER_DWELL_TIME`| `delta_min` $\in [-5, +15]$ | Extend or compress passenger dwell window | Train is currently dwelling; $t_{\text{dep}} \ge t_{\text{arr}} + d_{\text{min}}$ |
| `SPEED_THROTTLE` | `target_mps_kmh` $\in [30, 110]$ | Issue temporary caution order to regulate arrival spacing | Target section has high density or adverse weather |
| `REROUTE_DETOUR` | `detour_path` $= [v_1, \dots, v_m]$ | Divert train via parallel slow line or bypass chord | Detour path is physically connected and electrically compatible |
| `SECTION_ENTRY_HOLD`| `signal_id`, `hold_sec` $\in [60, 600]$ | Hold train at section entry home/starter signal | Downstream block section is saturated |
| `DO_NOTHING` | $\emptyset$ | Maintain standard timetable and signal progression | Default non-intervention baseline |

---

## 3. Precondition Filtering & Action Space Pruning

To ensure tractability and eliminate physically absurd options before neural scoring:

```python
def get_candidate_actions(state: RailwayState, target_train: TrainState) -> List[Action]:
    candidates = [Action(type="DO_NOTHING", train_id=target_train.id)]
    
    # Check station actions if train is near/at station
    if state.is_at_or_approaching_station(target_train):
        station = state.get_associated_station(target_train)
        
        # 1. Platform reassignment candidates
        for plt in station.platforms:
            if plt.is_free and plt.length_m >= target_train.length_m:
                candidates.append(Action(type="CHANGE_PLATFORM", train_id=target_train.id, new_platform_id=plt.id))
        
        # 2. Hold candidates
        for hold_time in [2, 5, 10, 15]:
            candidates.append(Action(type="HOLD_AT_STATION", train_id=target_train.id, duration_min=hold_time))
            
    # Check overtake / precedence actions if trailing train is higher priority
    trailing_train = state.get_immediate_follower(target_train)
    if trailing_train and trailing_train.priority > target_train.priority:
        nearest_loop_stn = state.get_next_loop_station(target_train)
        if nearest_loop_stn:
            candidates.append(Action(type="CHANGE_PRECEDENCE", train_id=target_train.id, 
                                     overtaking_train_id=trailing_train.id, loop_stn=nearest_loop_stn))
            
    # Check detour candidates if primary track is blocked/disrupted
    if state.is_downstream_disrupted(target_train):
        detours = state.find_valid_detour_paths(target_train)
        for path in detours:
            candidates.append(Action(type="REROUTE_DETOUR", train_id=target_train.id, detour_path=path))
            
    return candidates
```

---

## 4. Counterfactual Decision Tree Generation

During offline dataset creation, the **100,000 Scenario Engine** expands each scenario into a rich **Counterfactual Decision Tree**:

```
                                [ State S_0 (t=0) ]
                                         │
        ┌───────────────────┬────────────┴────────────┬───────────────────┐
        ▼                   ▼                         ▼                   ▼
   [ Action a_1 ]      [ Action a_2 ]            [ Action a_3 ]      [ Action a_4 ]
   Hold T12951 5m      Reroute T12951            Overtake at SUR      Do Nothing
        │                   │                         │                   │
        ▼                   ▼                         ▼                   ▼
  Simulator Rollout   Simulator Rollout         Simulator Rollout   Simulator Rollout
        │                   │                         │                   │
        ▼                   ▼                         ▼                   ▼
   State S'_{1}        State S'_{2}              State S'_{3}        State S'_{4}
   Delay: +14 min      Delay: +8 min             Delay: +42 min      Delay: +96 min
   Conflicts: 0        Conflicts: 0              Conflicts: 1        Conflicts: 3
   Safety: VALID       Safety: VALID             Safety: INVALID     Safety: INVALID
        │                   │                         │                   │
        └───────────────────┼─────────────────────────┴───────────────────┘
                            ▼
              [ CP-SAT Optimization Oracle ]
               Evaluates ground-truth cost J(a)
               Calculates preference ordering:
               [ a_2 ≻ a_1 ≻ a_3 ≻ a_4 (INVALID) ]
```

### Dataset Tuple Format
Each counterfactual training observation stored in the production shard contains:
$$\left( \mathcal{S}_t, \{a_1, a_2, \dots, a_K\}, \{\mathcal{C}(a_k)\}_{k=1}^K, \{\mathcal{J}(a_k)\}_{k=1}^K, a^*, \mathbf{r}^* \right)$$
where:
* $\{a_k\}_{k=1}^K$: Set of candidate dispatch actions.
* $\mathcal{C}(a_k) \in \{0, 1\}$: Binary deterministic safety validity.
* $\mathcal{J}(a_k)$: Evaluated multi-objective network cost.
* $a^* = \arg\min_{k, \mathcal{C}(a_k)=1} \mathcal{J}(a_k)$: Mathematically optimal action.
* $\mathbf{r}^* = \text{argsort}(\mathcal{J}(a_k))$: Full preference ranking vector over candidates.
