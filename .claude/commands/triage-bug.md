---
description: Triage a bug report into severity, likely area, repro steps and next action
argument-hint: <bug description or ticket text>
---

Triage this bug report:

$ARGUMENTS

Return a table with: **Severity** (S1-S4 with a one-line reason), **Likely area** (search the
repo with Grep/Glob and name candidate files), **Repro steps** (numbered, or "insufficient info"),
**Missing information** (specific questions), **Suggested next action** (one sentence).
Do not guess at a root cause; label anything unverified as a hypothesis.
