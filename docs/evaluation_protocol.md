# NEXUS AI — Scientific Evaluation Protocol & Benchmark Ladder (v1.0)

## 1. Evaluation Philosophy: Research Rigor

To prevent common failure modes in machine learning for transportation (such as data leakage, random row splitting, and overestimating performance on memorized topologies), NEXUS AI establishes a **4-tier scientific holdout evaluation protocol** and a progressive baseline benchmark ladder.

---

## 2. Dataset Splitting Methodology

```
                          100,000 SCENARIO DATASET
                                     │
      ┌──────────────────────────────┼──────────────────────────────┐
      ▼                              ▼                              ▼
70% Training Set              15% Validation Set             15% Test Holdouts
(70,000 Scenarios)            (15,000 Scenarios)             (15,000 Scenarios)
                                                                    │
                           ┌─────────────────┬──────────────────────┴──────────────────────┐
                           ▼                 ▼                      ▼                      ▼
                   Tier 1: Temporal  Tier 2: Geographic   Tier 3: Disruption     Tier 4: Historical
                       Holdout           Holdout              Holdout               Real Events
```

### 2.1 Tier 1: Temporal Holdout (Future Operational Periods)
* **Goal**: Measure performance on future time horizons never seen during training.
* **Protocol**: Train on historical periods $T_0 \to T_{\text{train}}$; validate on $T_{\text{train}} \to T_{\text{val}}$; test strictly on $T_{\text{test}} > T_{\text{val}}$.
* **Guarantees**: Zero information leakage from future timetable updates or seasonal weather shifts.

### 2.2 Tier 2: Geographic Holdout (Unseen Network Subdivisions)
* **Goal**: Measure inductive graph generalization to unseen railway topologies and track layouts.
* **Protocol**: Withhold 2 complete operational railway subdivisions (e.g., Vadodara-Ahmedabad or Sonipat-Panipat sections) from the training graph entirely.
* **Test**: Evaluate whether the graph neural network can reason over novel station degree distributions and track geometries without retraining.

### 2.3 Tier 3: Disruption Combination Holdout (Compositional Generalization)
* **Goal**: Test model resilience against unseen compound failure events.
* **Protocol**:
  * Training seen: Individual disruptions (e.g., Heavy Fog, Signal Failures, Platform Holds).
  * Testing evaluated: Novel compound pairs (e.g., `Heavy Fog + Route Interlocking Failure + Peak Passenger Demand`).

### 2.4 Tier 4: Historical Black-Swan Holdout (Real Incident Backtesting)
* **Goal**: Evaluate model decision quality against real documented major Indian Railways crisis events.
* **Protocol**: Replay real telemetry logs from documented historical disruption incidents, supply state $\mathcal{S}_0$, and compare model predictions and recommended interventions against actual historical outcomes and human dispatcher decisions.

---

## 3. The Baseline Benchmark Ladder

To demonstrate that the ~265M parameter capacity is experimentally justified, we benchmark against a rigorous 6-tier baseline ladder:

| Model Tier | Architecture | Approximate Parameters | Primary Role |
| :--- | :--- | :--- | :--- |
| **Baseline 1: Heuristic** | Rule-Based FIFO & Train Priority Ranking | $0$ | Standard dispatch baseline |
| **Baseline 2: Tabular ML** | LightGBM / XGBoost with engineered graph features | $\sim 500\text{K}$ | Standard non-deep tabular baseline |
| **Baseline 3: Small Spatial** | 2-Layer Spatio-Temporal GCN (ST-GCN) | $\sim 5\text{M}$ | Lightweight graph baseline |
| **Baseline 4: Mid GNN+Recurrent** | Relational GAT + GRU/LSTM Sequence Model | $\sim 35\text{M}$ | Classical spatiotemporal baseline |
| **Baseline 5: Scaling Family** | NEXUS-10M $\to$ 25M $\to$ 50M $\to$ 100M $\to$ 150M | $10\text{M} - 150\text{M}$ | Parameter scaling curve analysis |
| **Target: NEXUS-265M** | Hetero-GAT + Mamba-2 + Cross-Fusion Transformer | $\approx 265\text{M}$ | Full multimodal foundation model |
| **Oracle: CP-SAT Solver** | Exact Mixed-Integer / Constraint Programming (OR-Tools) | Exact Solver | Mathematical ground-truth upper bound |

---

## 4. Evaluation Metrics & Success Criteria

### 4.1 Predictive Accuracy Metrics
* **Mean Absolute Error (MAE)** & **RMSE**:
  $$\text{MAE}_{\text{delay}} = \frac{1}{N} \sum_{i=1}^N \left| y_i - \hat{y}_i \right|$$
* **Pinball Loss ($q=0.1, 0.5, 0.9$)**: Evaluates calibrated quantile delay uncertainty bands.
* **Macro F1-Score & AUROC**: Evaluates rare section conflict and interlocking collision detection.
* **Expected Calibration Error (ECE)**: Evaluates prediction confidence calibration.

### 4.2 Operational Decision Quality Metrics
* **Total Network Delay Savings**:
  $$\Delta \text{Delay} = \frac{\text{Delay}_{\text{Heuristic}} - \text{Delay}_{\text{NEXUS}}}{\text{Delay}_{\text{Heuristic}}} \times 100\%$$
* **Optimality Gap against CP-SAT Oracle**:
  $$\text{OptimalityGap} = \frac{\mathcal{J}_{\text{NEXUS}} - \mathcal{J}_{\text{CP-SAT}}}{|\mathcal{J}_{\text{CP-SAT}}|} \times 100\% \quad (\text{Target: } <5.0\%)$$
* **Hard Constraint Safety Violation Rate**:
  $$\text{ViolationRate} = \frac{\sum \mathbb{I}(\mathcal{C}_{\text{safety}} = 0)}{N_{\text{recommendations}}} \equiv \mathbf{0.00\%} \quad (\text{Mandatory Target})$$

### 4.3 Computational Latency Profile
* **Inference Latency Target**:
  * P50 Latency: $<25\text{ms}$
  * P95 Latency: $<45\text{ms}$
  * P99 Latency: $<50\text{ms}$
* **Optimization Oracle Speedup**: $\ge 100\times$ faster runtime compared to re-solving the full CP-SAT MILP from scratch.

---

## 5. Master Ablation Study Matrix

| Ablation Study | Experimental Configurations | Scientific Hypothesis |
| :--- | :--- | :--- |
| **A: Data Grounding** | (1) Real data only<br>(2) Synthetic data only<br>(3) Real + Calibrated Synthetic | Combining real historical ground-truth with counterfactual digital twin simulation produces superior generalization on locked test sets. |
| **B: Spatial Modeling** | (1) No Graph (MLP)<br>(2) Homogeneous GCN<br>(3) Heterogeneous GAT with edge conditioning | Heterogeneous multi-relation message passing is required to capture train-station-section interlocking dynamics. |
| **C: Temporal Dynamics**| (1) Static Snapshot<br>(2) LSTM/GRU<br>(3) Causal Mamba-2 Sequence Backbone | Causal linear-time state-space models scale to 128 time steps without quadratic memory bottlenecks or temporal leakage. |
| **D: Curriculum Stages** | (1) Direct End-to-End Supervised<br>(2) Multi-Stage Curriculum (Stages 1 $\to$ 5) | Progressive pretraining (topology $\to$ dynamics $\to$ multitask $\to$ policy) avoids representation collapse. |
| **E: Safety Validator** | (1) Unconstrained Neural Policy<br>(2) Dual-Verifier with Hard Deterministic Gate | Neural models alone produce $\approx 1-3\%$ edge-case violations; deterministic gate guarantees absolute zero safety violations. |
