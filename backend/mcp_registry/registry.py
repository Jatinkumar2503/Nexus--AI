"""A small, explicit registry for planner-accessible internal tools.

Tools are registered in-process rather than exposed as arbitrary Python calls.  This
keeps the planning boundary allowlisted and makes it straightforward to audit which
simulation capabilities an agent may invoke.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable


ToolHandler = Callable[..., Dict[str, Any]]


class ToolRegistryError(ValueError):
    """Raised when a caller requests an unavailable planner tool."""


@dataclass(frozen=True)
class ToolSpec:
    """Description and handler for one allowlisted internal tool."""

    name: str
    description: str
    handler: ToolHandler
    input_schema: Dict[str, Any]

    def public_definition(self) -> Dict[str, Any]:
        """Return the serializable definition exposed to the planner."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.input_schema,
        }


class ToolRegistry:
    """Stores and executes named, allowlisted planning tools."""

    def __init__(self) -> None:
        self._tools: Dict[str, ToolSpec] = {}

    def register(self, tool: ToolSpec) -> None:
        if tool.name in self._tools:
            raise ToolRegistryError(f"Tool '{tool.name}' is already registered.")
        self._tools[tool.name] = tool

    def get(self, name: str) -> ToolSpec:
        try:
            return self._tools[name]
        except KeyError as exc:
            raise ToolRegistryError(f"Tool '{name}' is not allowlisted.") from exc

    def execute(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(arguments, dict):
            raise ToolRegistryError("Tool arguments must be an object.")
        return self.get(name).handler(**arguments)

    def definitions(self) -> Iterable[Dict[str, Any]]:
        return [tool.public_definition() for tool in self._tools.values()]
