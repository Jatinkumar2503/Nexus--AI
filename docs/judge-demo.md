# NEXUS AI judge demo

## Two-minute storyline

1. Start on the cockpit. The header confirms the planner mode and the live event
   stream status.
2. Inject cascading incident or network partition from the incident dialog. The
   digital twin immediately shows a disrupted corridor and updated metrics.
3. Generate a plan. Show the structured recommendation, confidence, risks,
   assumptions, recovery timeline, alternatives, and predicted metrics.
4. Open the execution stream to show planner, allowlisted tool, validation, and
   decision events. In enhanced mode, point out the provider and tool-call count;
   in local mode, point out deterministic recovery and no external dependency.
5. Validate, approve, and commit the plan. Show the audit event and replay
   timeline to demonstrate human authority and incident traceability.

## Enhanced-mode proof

When a provider credential is configured, begin with PLANNER_MODE=enhanced.
During planning, point to the model name, approved tool-call count, structured
recommendation, and validation result. If the provider fails, deliberately
switch to the same incident in PLANNER_MODE=auto and show that the local
planner returns the identical typed contract with a visible fallback reason.

## Outcome narrative

Use the cascading incident preset and state the operator consequence before
clicking anything: the dispatch desk must protect a constrained corridor,
passenger service, crew compliance, and traction safety at the same time.
After commit, compare the plan prediction with live delay, energy, and
resilience metrics, then load replay to show the accountable decision trail.

## Judge talking points

- The SimPy and NetworkX digital twin provides grounded operational evidence.
- The local rule engine is deterministic, explainable, and always available.
- Optional Responses API enhancement uses only a strict, read-only tool
  allowlist; validation retains final safety authority.
- Every decision is typed, replayable, auditable, and cannot execute without
  explicit dispatcher approval.

## Demo-safe recovery

If an enhanced provider is unavailable, keep PLANNER_MODE=local or
PLANNER_MODE=auto. The dashboard continues with the same plan contract and
identifies the local fallback rather than presenting a failed planner.
