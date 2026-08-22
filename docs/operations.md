# Production operations guide

## Required configuration

Copy `backend/.env.example` to a protected environment file or set equivalent
platform secrets. Set `NEXUS_AUTH_REQUIRED=true`, a long unique
`NEXUS_DISPATCHER_TOKEN`, an operator identity, exact dashboard origins in
`NEXUS_CORS_ORIGINS`; the local planner requires no model credentials. To enable
optional enhanced planning, set `PLANNER_MODE=auto` or `PLANNER_MODE=enhanced`,
`OPENAI_API_KEY`, and optionally `OPENAI_MODEL=gpt-5`. The service always
falls back to the local rule engine if the provider is unavailable.
Do not expose these values in frontend variables, logs, source control, or CI
output.

## Start and health check

Install backend dependencies and run `python backend/main.py`. Confirm the
service readiness probe before admitting traffic:

```bash
curl http://127.0.0.1:8000/healthz
```

It returns a healthy status only after the SQLite operational store can be
opened. The production database is `backend/data/nexus.db`; place this path on
durable encrypted storage and run a single application process per SQLite file.

## Backup and recovery

Pause writes during backup or use SQLite's online backup command, then encrypt
and retain a dated copy of `nexus.db`. Regularly restore a copy into an isolated
environment and call `/healthz`. The initial startup migration imports legacy
`plans.json` and `recovery_memory.json` only when the database tables are empty.

## Dispatcher access and audit

Approval, commit, and audit reads accept `Authorization: Bearer <token>` when
authentication is enabled. Successful approvals and commits append actor,
action, plan ID, strategy, and timestamp to the SQLite audit log. Review
`GET /api/audit-events` during incident investigation; database access should be
restricted so the audit table is not modified outside the service.

## Incident runbook

1. Stop dispatcher commits if a recommendation is suspect; do not delete plan records.
2. Preserve the database, application logs, and audit records.
3. Inspect the affected plan and audit events, then validate a new plan before approval.
4. Rotate `NEXUS_DISPATCHER_TOKEN` if exposure is suspected.
5. Restore the latest verified backup only after recording the incident and impact.

## Release gate

GitHub Actions runs backend contracts, frontend unit tests, production build,
and Chromium smoke coverage. Deploy only a green commit. For a live acceptance
check, verify the local fallback first:

```bash
curl http://127.0.0.1:8000/api/planner/status
```

When enhanced mode is configured, submit the normal planner request and confirm
the response metadata reports either the enhanced provider or a safe local fallback.
