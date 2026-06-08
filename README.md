# NEXUS: Multi-Agent Rail Network Operations Simulator

NEXUS is a real-time Decision Support System (DSS) designed for railway dispatchers to simulate and evaluate the downstream consequences of service recovery decisions during network disruptions.

## 🚀 Key Features
* **Multi-Agent Simulation (MAS)**: Individual autonomous agents modeling trains, stations/junctions, and crews.
* **Dynamic Disruption Simulation**: Inject signal failures, track blockages, or train faults directly from the interactive map.
* **Three-Way Scenario Analysis**: Instantly compare recovery options (e.g., Do Nothing, Detouring, and Short-Turning) side-by-side.
* **Multi-Dimensional Metrics**: Live evaluation of passenger delay-minutes, crew schedule compliance, and power grid energy costs.
* **LLM Explainability**: Natural language summaries of agent negotiations and recommendations.

## 🛠️ Architecture
* **Frontend**: React + TypeScript + Vite + Tailwind CSS + MapLibre GL JS
* **Backend**: FastAPI + NetworkX (Graph Topology) + SimPy (Discrete Event Simulation)


