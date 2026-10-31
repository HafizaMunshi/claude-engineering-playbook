---
name: adr-writer
description: Use when a technical decision has been made or must be made (library choice, data model, service boundary, build vs buy) and needs an Architecture Decision Record in docs/adr/.
---

# ADR writer

## Procedure
1. Find the next number: list `docs/adr/` and increment (`0007-...`). Create the folder if missing.
2. Ask only for what you cannot infer: the decision, the deciders, and any hard constraints.
3. Write the ADR with the sections below. Keep it to one page.
4. Present at least two real alternatives with honest downsides; "do nothing" counts as one.

## Format (`docs/adr/NNNN-kebab-title.md`)
```
# NNNN. <Decision as a short imperative phrase>

Status: proposed | accepted | superseded by NNNN
Date: <YYYY-MM-DD>

## Context
<Forces at play: requirements, constraints, scale, team skills. Facts, not opinions.>

## Decision
<What we will do, in active voice.>

## Alternatives considered
- <Option A> - pros / cons
- <Option B> - pros / cons

## Consequences
Positive: ...
Negative / risks: ...
Revisit when: <measurable trigger>
```

## Rules
- Never edit an accepted ADR; supersede it with a new one.
- Record the trade-off you accepted, not just the winner.
