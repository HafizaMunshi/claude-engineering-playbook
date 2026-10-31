# CLAUDE.md - <service-name> (backend REST service)

## Purpose
<One sentence: what the service owns and who calls it.>

## Commands
```bash
./run test            # unit tests
./run lint            # static analysis
./run dev             # local server on :8080
```

## Architecture
- Layers: controller -> service -> repository. Controllers hold no business logic.
- Outbound HTTP goes through one client class with timeouts + retries on 5xx only.
- Config comes from environment; never read secrets from files in the repo.

## Conventions
- Validate every request field at the edge; any value placed in an outbound URL or SQL fragment needs an allow-list or parameter binding.
- DB migrations are append-only: add a new dated file, never edit a committed one.
- Errors: return typed problem responses; never leak stack traces.
- New endpoint checklist: authz, input validation, tests (happy + 2 failure paths), OpenAPI update.

## Guardrails for Claude
- Ask before changing security config, build pipeline, or shared libraries.
- Do not run migrations or write SQL against shared environments; output SQL for review instead.
- Run the test command before declaring a task done.
