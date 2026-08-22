"""NEXUS AI — Baseline Heuristic Dispatchers.

Implements rule-based dispatchers for comparison:
1. FIFO (First-In, First-Out): Dispatches trains strictly in arrival sequence.
2. Priority-First: Dispatches trains by train priority class (Vande Bharat > Rajdhani > Freight).
3. Delay-Equalization: Dispatches whichever train currently suffers the highest accumulated delay.
"""

from typing import List, Dict, Any

class HeuristicDispatcher:
    def __init__(self, mode: str = "priority_first"):
        self.mode = mode

    def select_action(self, candidate_actions: List[Dict[str, Any]], train_priorities: Dict[str, float], train_delays: Dict[str, float]) -> Dict[str, Any]:
        """Selects best candidate action according to heuristic policy."""
        if not candidate_actions:
            return {"action_type": "do_nothing"}

        if self.mode == "fifo":
            return candidate_actions[0]

        if self.mode == "priority_first":
            # Prefer actions that prioritize higher-weight trains or resolve their conflicts
            scored = []
            for act in candidate_actions:
                tid = act.get("train_id", "")
                prio = train_priorities.get(tid, 1.0)
                act_type = act.get("action_type", "do_nothing")
                # High priority train should not be held
                score = prio * (0.5 if act_type == "hold" else 1.5)
                scored.append((act, score))
            scored.sort(key=lambda x: x[1], reverse=True)
            return scored[0][0]

        if self.mode == "delay_equalization":
            # Prioritize the train with the worst current delay
            scored = []
            for act in candidate_actions:
                tid = act.get("train_id", "")
                delay = train_delays.get(tid, 0.0)
                scored.append((act, delay))
            scored.sort(key=lambda x: x[1], reverse=True)
            return scored[0][0]

        return candidate_actions[0]
