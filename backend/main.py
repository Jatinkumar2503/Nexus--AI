import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from simulation.topology import RailTopology

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("nexus-api")

app = FastAPI(
    title="NEXUS API",
    description="Backend API and Simulation Engine for NEXUS Rail Network Operations Simulator",
    version="1.0.0"
)

# Initialize rail network topology
topology = RailTopology()

# Set up CORS middleware for integration with the React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify the actual frontend origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    """API health-check root endpoint."""
    return {
        "status": "healthy",
        "service": "NEXUS Rail Operations Simulator API",
        "version": "1.0.0"
    }

@app.get("/api/health")
async def health():
    """Detailed health check endpoint."""
    return {
        "status": "ok",
        "components": {
            "api": "online",
            "simulation_engine": "initialized"
        }
    }

@app.get("/api/topology")
async def get_topology():
    """Fetch the rail network nodes and edges."""
    return {
        "status": "success",
        "nodes": topology.get_nodes(),
        "edges": topology.get_edges()
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
