"""Read-only NetworkX topology tools available to the Planner Agent."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from simulation.topology import RailTopology

from .registry import ToolSpec


EMPTY_OBJECT_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {},
    "additionalProperties": False,
}


def get_network_topology(topology: RailTopology) -> Dict[str, Any]:
    """Return a compact, read-only view of stations and directed segments."""
    return {
        "nodes": topology.get_nodes(),
        "edges": topology.get_edges(),
    }


def find_recovery_path(
    topology: RailTopology,
    origin: str,
    destination: str,
    blocked_edges: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Find the least-travel-time permitted path using the existing topology."""
    path = topology.get_path(origin, destination, blocked_edges=blocked_edges)
    return {
        "origin": origin,
        "destination": destination,
        "blocked_edges": blocked_edges or [],
        "path": path,
        "found": bool(path),
    }


def build_planning_tools(topology: RailTopology) -> List[ToolSpec]:
    """Build planner tool specifications bound to one topology instance."""
    return [
        ToolSpec(
            name="get_network_topology",
            description="Get the current rail stations and directed track segments.",
            handler=lambda: get_network_topology(topology),
            input_schema=EMPTY_OBJECT_SCHEMA,
        ),
        ToolSpec(
            name="find_recovery_path",
            description="Find a shortest permitted path while avoiding blocked segments.",
            handler=lambda origin, destination, blocked_edges=None: find_recovery_path(
                topology, origin, destination, blocked_edges
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "origin": {"type": "string"},
                    "destination": {"type": "string"},
                    "blocked_edges": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "required": ["origin", "destination"],
                "additionalProperties": False,
            },
        ),
    ]
