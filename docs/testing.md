# Tests

Run the offline checks with:

```bash
bash scripts/verify.sh
```

The verification script runs Ruff, all Python tests with branch coverage, frontend
component tests, TypeScript checking, and a production frontend build. Weather
tests use HTTPX's in-memory transport and never call Open-Meteo.
It enforces at least 85% Python line coverage and 80% branch coverage.

Run the opt-in container smoke test separately when Docker is available:

```bash
bash scripts/docker-smoke.sh
```

It builds the production image, starts the single container, and checks readiness
and the SPA. It does not spend an external weather request.
