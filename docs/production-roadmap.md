# Production-readiness roadmap

This roadmap builds on the working simulator, planner, dispatcher lifecycle, and
dashboard. Each phase has a deployable outcome and is committed independently.

1. **Quality gates (in progress)** — Browser smoke coverage and GitHub Actions
   run backend contracts, frontend tests, the production build, and E2E checks.
2. **Durable persistence** — Migrate plans, recovery outcomes, and preferences
   from JSON files to a database with migrations and repository tests.
3. **Dispatcher security and audit** — Add authenticated dispatcher identity,
   role-based approval/commit authorization, and immutable audit events.
4. **Operational UX and performance** — Add replay seek controls and reduce the
   deferred map payload without regressing the control-room workflow.
5. **Deployment readiness** — Document configuration, secrets, health checks,
   backups, CI/CD, and incident response; add production-safe settings.
6. **Local acceptance check** — Run the non-mutating rule-based planner verification through `POST /api/planner`
   against a configured project key and record its result outside source control.

The current execution order intentionally completes test gates before changing
persistence or authorization, so later architectural work is protected by
repeatable regression checks.
