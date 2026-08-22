"""Optional OpenAI-enhanced planning with deterministic local fallback."""
from __future__ import annotations

import asyncio
import json
import logging
import os
from time import perf_counter
from typing import Literal

from mcp_registry.default_registry import build_default_registry
from agents.events import execution_events
from agents.validator import ValidationAgent
from simulation.engine import SimulationEngine
from simulation.models import PlannerMetadata, PlannerRequest, RecoveryPlan, ValidationRequest
from simulation.topology import RailTopology
from services.planner_engine import generate_recovery_plan

logger = logging.getLogger("nexus.planner")
PlannerMode = Literal["local", "auto", "enhanced"]
_openai_client: object | None = None
_openai_client_key: str | None = None


def configured_planner_mode() -> PlannerMode:
    mode = os.getenv("PLANNER_MODE", "local").strip().lower()
    return mode if mode in {"local", "auto", "enhanced"} else "local"


def configured_model() -> str:
    return os.getenv("OPENAI_MODEL", "gpt-5")


def get_openai_client() -> object:
    """Create one server-side Responses client per configured API key."""
    global _openai_client, _openai_client_key
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OpenAI is not configured")
    if _openai_client is None or _openai_client_key != api_key:
        try:
            from openai import AsyncOpenAI
        except ImportError as exc:
            raise RuntimeError("OpenAI SDK is not installed") from exc
        _openai_client = AsyncOpenAI(api_key=api_key, timeout=float(os.getenv("OPENAI_TIMEOUT_SECONDS", "20")), max_retries=1)
        _openai_client_key = api_key
    return _openai_client


class PlannerService:
    """Uses OpenAI only when enabled; every failure returns a local plan."""

    def __init__(self, engine: SimulationEngine, topology: RailTopology):
        self._engine = engine
        self._topology = topology

    async def plan(self, request: PlannerRequest) -> RecoveryPlan:
        started = perf_counter()
        mode = configured_planner_mode()
        if mode == "local":
            return self._local(request, started)
        if not os.getenv("OPENAI_API_KEY"):
            return self._local(request, started, "OpenAI is not configured.")
        try:
            plan, tool_calls = await self._enhanced(request)
            validation = ValidationAgent(self._engine).validate(ValidationRequest(plan=plan))
            if not validation.is_valid:
                raise RuntimeError("Enhanced plan failed local validation")
            elapsed = int((perf_counter() - started) * 1000)
            plan.planner_metadata = PlannerMetadata(mode="enhanced", provider="openai", model=configured_model(), latency_ms=elapsed, execution_time_ms=elapsed, tool_calls=tool_calls)
            return plan
        except Exception as exc:
            logger.warning("Enhanced planner fallback: %s", type(exc).__name__)
            return self._local(request, started, "Enhanced planner unavailable: " + type(exc).__name__ + ".")

    def _local(self, request: PlannerRequest, started: float, reason: str | None = None) -> RecoveryPlan:
        plan = generate_recovery_plan(request.disruption, request.trains, request.stations)
        plan.planner_metadata = PlannerMetadata(mode="local", provider="local", execution_time_ms=int((perf_counter() - started) * 1000), fallback_reason=reason)
        return plan

    async def _enhanced(self, request: PlannerRequest) -> tuple[RecoveryPlan, int]:
        registry = build_default_registry(self._engine, self._topology)
        timeout = float(os.getenv("OPENAI_TIMEOUT_SECONDS", "20"))
        client = get_openai_client()
        inputs: list[object] = [
            {"role": "system", "content": "You are a railway recovery analyst. Return only schema-valid JSON. Use only approved tools and do not propose unsafe actions."},
            {"role": "user", "content": json.dumps(request.model_dump(mode="json"))},
        ]
        tool_count = 0
        for _ in range(3):
            execution_events.emit("planner", "OpenAI enhanced planner is evaluating the disruption.")
            response = await asyncio.wait_for(
                client.responses.create(
                    model=configured_model(), input=inputs,
                    text={"format": {"type": "json_schema", "name": "recovery_plan", "schema": RecoveryPlan.model_json_schema(), "strict": True}},
                    tools=[{"type": "function", **tool} for tool in registry.definitions()],
                ), timeout=timeout,
            )
            calls = [item for item in response.output if item.type == "function_call"]
            if not calls:
                return RecoveryPlan.model_validate_json(response.output_text), tool_count
            tool_count += len(calls)
            if tool_count > 6:
                raise RuntimeError("Tool-call budget exceeded")
            inputs.extend(response.output)
            for call in calls:
                execution_events.emit("tool", "Calling approved tool: " + call.name)
                arguments = json.loads(call.arguments)
                result = registry.execute(call.name, arguments)
                inputs.append({"type": "function_call_output", "call_id": call.call_id, "output": json.dumps(result)})
                execution_events.emit("tool", "Approved tool finished: " + call.name)
        raise RuntimeError("Tool-call recursion limit exceeded")
