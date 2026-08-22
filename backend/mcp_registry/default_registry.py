"""Composition root for the planner's allowlisted internal tools."""

from simulation.engine import SimulationEngine
from simulation.topology import RailTopology

from .analytics_tools import build_analytics_tools
from .planning_tools import build_planning_tools
from .registry import ToolRegistry
from .simulation_tools import build_simulation_tools
from .scenario_tools import build_scenario_tools
from .intelligence_tools import build_intelligence_tools


def build_default_registry(engine: SimulationEngine, topology: RailTopology) -> ToolRegistry:
    """Create the complete read-only registry used by the Milestone 1 planner."""
    registry = ToolRegistry()
    for tool in (
        *build_planning_tools(topology),
        *build_simulation_tools(engine),
        *build_analytics_tools(engine),
        *build_scenario_tools(engine),
        *build_intelligence_tools(engine),
    ):
        registry.register(tool)
    return registry
