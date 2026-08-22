# NEXUS AI architecture

NEXUS is a human-governed railway recovery system. The SimPy and NetworkX digital twin remains the operational source of truth; the planner never commits an action directly.

```mermaid
sequenceDiagram
  participant D as Dispatcher
  participant UI as React cockpit
  participant API as FastAPI
  participant P as Planner
  participant T as Approved tools
  participant V as Validation
  participant S as SimPy/NetworkX twin
  participant A as Audit and replay store
  D->>UI: Inject incident
  UI->>API: Create disruption
  API->>S: Update live twin
  UI->>API: Request plan
  API->>P: Local or enhanced planner
  P->>T: Read-only operational evidence
  P->>V: Typed recommendation
  V->>S: Sandbox validation
  V-->>UI: Validated plan and alternatives
  D->>UI: Approve then commit
  UI->>API: Lifecycle transition
  API->>S: Apply safe strategy
  API->>A: Persist audit and replay event
```

## Safety boundaries

- The local rule engine is the default and requires no external credential.
- Enhanced mode uses structured Responses API output and an explicit read-only tool allowlist.
- Validation rejects unsupported, ungrounded, illegal, or crew-unsafe plans.
- Dispatcher approval is required before every commit or rollback.
- Replay and audit events are persisted in SQLite.
