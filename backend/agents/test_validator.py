import unittest
from pydantic import ValidationError
from agents.validator import ValidationAgent
from simulation.engine import SimulationEngine
from simulation.models import RecoveryAction, ValidationRequest

def request(strategy):
    return ValidationRequest.model_validate({"plan":{"recommended_strategy":strategy,"confidence_score":0.8,"primary_reasoning":"test","actions":[],"expected_metrics":{"delay_minutes":1,"energy_kwh":1,"crew_violations":0,"resilience_score":90}},"monte_carlo_runs":1})

class TestValidationAgent(unittest.TestCase):
    def test_rejects_unsupported_strategy(self):
        with self.assertRaises(ValidationError):
            request("invalid")

    def test_requires_sandbox_evidence(self):
        result = ValidationAgent(SimulationEngine()).validate(request("detour"))
        self.assertFalse(result.is_valid)
        self.assertEqual(result.findings[0].code, "scenario_unavailable")

    def test_rejects_action_with_unknown_train_or_location(self):
        payload = request("detour")
        payload.plan.actions = [RecoveryAction(train_id="unknown", action_type="hold", location="unknown")]
        result = ValidationAgent(SimulationEngine()).validate(payload)
        self.assertFalse(result.is_valid)
        self.assertEqual({item.code for item in result.findings}, {"unknown_train", "unknown_location"})
