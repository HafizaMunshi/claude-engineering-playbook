---
description: Draft a pull-request title and description from the current branch
argument-hint: [base-branch]
allowed-tools: Bash(git diff:*), Bash(git log:*), Bash(git status:*)
---

Base branch: $ARGUMENTS (if empty, assume main)

Commits on this branch:
!`git log --oneline origin/main..HEAD 2>/dev/null || git log --oneline -10`

Diff summary:
!`git diff --stat HEAD~1 2>/dev/null || git diff --stat`

Write a PR description with: a title under 70 characters, **What changed** (3-5 bullets),
**Why**, **How to test** (exact commands), **Risks / rollback**. Do not invent details
not visible in the commits or diff.
