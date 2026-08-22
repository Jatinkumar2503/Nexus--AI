"""Translation between planner recommendations and simulator policies.

The planner may express an operationally rich recommendation while the
SimPy engine intentionally supports a smaller set of executable policies.
Keeping this mapping in one place prevents an approved plan from becoming a
no-op at commit time.
"""

from typing import Literal


SimulatorStrategy = Literal["do_nothing", "detour", "short_turn"]

_SIMULATOR_STRATEGIES: dict[str, SimulatorStrategy] = {
    "do_nothing": "do_nothing",
    "detour": "detour",
    "short_turn": "short_turn",
    "reroute": "detour",
    "reroute_and_prioritize": "detour",
    "mixed_strategy": "detour",
    "hold": "do_nothing",
    "crew_swap": "do_nothing",
    "inspection": "do_nothing",
}


def simulation_strategy_for(recommended_strategy: str) -> SimulatorStrategy:
    """Return the safe executable policy for a planner recommendation.

    Raises ``ValueError`` rather than silently applying an unknown policy.
    """
    try:
        return _SIMULATOR_STRATEGIES[recommended_strategy]
    except KeyError as exc:
        raise ValueError(f"Unsupported recovery strategy: {recommended_strategy}") from exc
