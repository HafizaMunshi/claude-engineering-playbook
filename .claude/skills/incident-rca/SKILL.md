---
name: incident-rca
description: Use after a production incident or recurring bug to run a blameless root-cause analysis (timeline, five whys, contributing factors, prevention actions). Triggers on words like postmortem, RCA, outage, regression, "why did this happen".
---

# Incident RCA

Evidence first, narrative second. Every claim in the RCA must point at a log line,
commit, metric, or ticket - otherwise label it **hypothesis**.

## Steps
1. **Collect evidence** - alerts, error logs, deploy history (`git log --since`), config changes, dashboards. List sources used.
2. **Timeline** (UTC): detection -> impact start -> mitigation -> resolution. Note the gap between impact start and detection.
3. **Impact**: who/what was affected, for how long, and how it was measured.
4. **Five whys**: keep asking "why" until you reach a process or design gap, not a person. Stop when the answer is something a team can change.
5. **Contributing factors**: use categories - code, config, data, infra, process, monitoring. A single incident usually has 2-4.
6. **Fix and prevent**: separate *immediate fix*, *detection improvement*, *prevention*. Each action has an owner role and a checkable done-condition.

## Template
Use `templates/rca.md` in this skill folder. Fill every section; write "unknown - needs <evidence>" rather than inventing.

## Rules
- Blameless language: "the deploy lacked a check", not "X forgot".
- Never state a root cause as proven when only one data point supports it.
- Keep the final document under two pages.
