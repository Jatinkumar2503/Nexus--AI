"""Enhanced-mode fallback tests; no network or API key is required."""
import asyncio
import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from services import planner_service
from services.planner_service import PlannerService
from simulation.engine import SimulationEngine
from simulation.models import Disruption, PlannerRequest
from simulation.models import ValidationResult
from services.planner_engine import generate_recovery_plan


class PlannerServiceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        planner_service._openai_client = None
        planner_service._openai_client_key = None

    def test_openai_client_is_reused_for_same_key(self):
        factory = Mock(return_value=object())
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}), patch.dict(sys.modules, {"openai": SimpleNamespace(AsyncOpenAI=factory)}):
            self.assertIs(planner_service.get_openai_client(), planner_service.get_openai_client())
        factory.assert_called_once()

    async def test_enhanced_mode_without_key_returns_local_plan(self):
        engine = SimulationEngine()
        request = PlannerRequest(disruption=Disruption(id="D1", edge_id="MUM->TNA", duration=30, severity="HIGH"), trains=[], stations=[])
        with patch.dict(os.environ, {"PLANNER_MODE": "enhanced"}, clear=False):
            os.environ.pop("OPENAI_API_KEY", None)
            plan = await PlannerService(engine, engine.topology).plan(request)
        self.assertEqual(plan.planner_metadata.mode, "local")
        self.assertIn("not configured", plan.planner_metadata.fallback_reason)

    async def test_provider_failures_always_return_local_fallback(self):
        engine = SimulationEngine()
        request = PlannerRequest(disruption=Disruption(id="D1", edge_id="MUM->TNA", duration=30, severity="HIGH"), trains=[], stations=[])
        for failure in (asyncio.TimeoutError(), RuntimeError("rate limited"), ValueError("malformed response")):
            with self.subTest(failure=type(failure).__name__), patch.dict(os.environ, {"PLANNER_MODE": "enhanced", "OPENAI_API_KEY": "test-key"}), patch.object(PlannerService, "_enhanced", new=AsyncMock(side_effect=failure)):
                plan = await PlannerService(engine, engine.topology).plan(request)
                self.assertEqual(plan.planner_metadata.mode, "local")
                self.assertIn("Enhanced planner unavailable", plan.planner_metadata.fallback_reason)

    async def test_valid_enhanced_result_records_mode_and_tool_count(self):
        engine = SimulationEngine()
        request = PlannerRequest(disruption=Disruption(id="D1", edge_id="MUM->TNA", duration=30, severity="HIGH"), trains=[], stations=[])
        enhanced = generate_recovery_plan(request.disruption, request.trains, request.stations)
        valid = Mock(is_valid=True)
        with patch.dict(os.environ, {"PLANNER_MODE": "enhanced", "OPENAI_API_KEY": "test-key"}), patch.object(PlannerService, "_enhanced", new=AsyncMock(return_value=(enhanced, 2))), patch("services.planner_service.ValidationAgent") as validator:
            validator.return_value.validate.return_value = valid
            plan = await PlannerService(engine, engine.topology).plan(request)
        self.assertEqual(plan.planner_metadata.mode, "enhanced")
        self.assertEqual(plan.planner_metadata.tool_calls, 2)

    async def test_enhanced_responses_shape_parses_structured_output(self):
        engine = SimulationEngine()
        request = PlannerRequest(disruption=Disruption(id="D1", edge_id="MUM->TNA", duration=30, severity="HIGH"), trains=[], stations=[])
        expected = generate_recovery_plan(request.disruption, request.trains, request.stations)
        response = SimpleNamespace(output=[], output_text=expected.model_dump_json())
        client = SimpleNamespace(responses=SimpleNamespace(create=AsyncMock(return_value=response)))
        with patch("services.planner_service.get_openai_client", return_value=client):
            plan, tool_count = await PlannerService(engine, engine.topology)._enhanced(request)
        self.assertEqual(plan.recommended_strategy, expected.recommended_strategy)
        self.assertEqual(tool_count, 0)
