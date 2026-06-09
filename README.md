# NEXUS: Multi-Agent Rail Network Operations Simulator

NEXUS is a real-time Decision Support System (DSS) designed for railway dispatchers to simulate and evaluate the downstream consequences of service recovery decisions during network disruptions.

## 🚀 Key Features
* **Multi-Agent Simulation (MAS)**: Individual autonomous agents modeling trains, stations/junctions, and crews.
* **Dynamic Disruption Simulation**: Inject signal failures, track blockages, or train faults directly from the interactive map.
* **Three-Way Scenario Analysis**: Instantly compare recovery options (e.g., Do Nothing, Detouring, and Short-Turning) side-by-side.
* **Multi-Dimensional Metrics**: Live evaluation of passenger delay-minutes, crew schedule compliance, and power grid energy costs.
* **LLM Explainability**: Natural language summaries of agent negotiations and recommendations.

## 🛠️ Architecture
* **Frontend**: React + TypeScript + Vite + Tailwind CSS v4 + MapLibre GL JS
* **Backend**: FastAPI + NetworkX (Graph Topology) + SimPy (Discrete Event Simulation)

## 🚦 How to Run the System

### Prerequisites
* Python 3.10+
* Node.js 18+

### 1. Start the FastAPI Simulation Backend
```bash
cd backend
# Create virtual environment if needed: python -m venv venv
# Activate virtualenv:
# Windows: .\venv\Scripts\activate  |  macOS/Linux: source venv/bin/activate
pip install -r requirements.txt
python main.py
```

### 2. Start the React Frontend Dashboard
```bash
cd frontend
npm install
npm run dev
```

### 3. Running Automated Tests
```bash
python backend/simulation/test_simulator.py
```


