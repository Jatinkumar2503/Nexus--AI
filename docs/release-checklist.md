# Release checklist

- Backend quality suite passes.
- Frontend unit tests, lint, build, and responsive Playwright suites pass.
- Health endpoint reports SQLite availability.
- Local planner works without a provider credential.
- Enhanced mode falls back safely when the provider is unavailable.
- Dispatcher lifecycle covers validate, approve, commit, rollback, audit, and replay.
- Configure exact production CORS origins and a dispatcher token before deployment.
- Perform one live enhanced-mode smoke test only after setting the provider key.
