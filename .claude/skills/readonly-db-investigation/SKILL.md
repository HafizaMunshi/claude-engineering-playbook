---
name: readonly-db-investigation
description: Use when you need to look at data in a relational database to debug an issue (duplicates, missing rows, stale values, counts that do not add up). Runs SELECT-only queries through a guarded helper and never writes.
---

# Read-only database investigation

Writes are never executed by Claude. If a fix is needed, produce the SQL as text for a human to review and run.

## Procedure
1. State the question as a falsifiable hypothesis ("there are two active rows per customer").
2. Learn the schema first: `python .claude/skills/readonly-db-investigation/scripts/safe_query.py <db> --schema`.
3. Write the smallest SELECT that can confirm or refute the hypothesis. Always include `LIMIT` unless aggregating.
4. Run it through the helper:
   `python .claude/skills/readonly-db-investigation/scripts/safe_query.py <db> "SELECT ..."`
   The helper rejects anything that is not a single SELECT/WITH statement and opens the database read-only.
5. Report: the query, the result (compact table), what it proves, and what it does *not* prove.
6. If remediation is needed, output three blocks: **verify** SELECT, **fix** statement (text only, wrapped in a transaction with a row-count check), **validate** SELECT.

## Rules
- Never paste connection strings or credentials into chat, files or commands; take them from the environment.
- Never `SELECT *` on wide tables in front of the user; name columns.
- Mask personal data in anything you summarise.
