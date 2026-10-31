# CLAUDE.md - <pipeline-name> (batch data pipeline)

## Purpose
<Sources -> transforms -> sinks, schedule, and the SLA.>

## Commands
```bash
pytest tests/unit                 # fast tests, no network
pytest tests/integration -m slow  # needs local containers
python -m pipeline.run --date 2026-01-01 --dry-run
```

## Principles
- Idempotent: re-running a date must produce the same output (upsert or overwrite partitions, never append blindly).
- Every stage logs row counts in/out; a >5% unexplained drop fails the run.
- Schemas are explicit (pydantic or typed dataframes); no silent type coercion.

## Conventions
- Pure transform functions in `transforms/`, I/O only in `io/`.
- Backfills run through the same code path as daily runs with a date range.
- Never read production credentials in tests; use fixtures under `tests/data/`.

## Guardrails for Claude
- Dry-run by default; never target a production sink without explicit user confirmation.
- When investigating bad data, SELECT only; present fix SQL as text.
