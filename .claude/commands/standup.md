---
description: Generate a concise daily standup update from yesterday's git activity
allowed-tools: Bash(git log:*), Bash(git status:*), Bash(git config:*)
---

My recent commits (last 24h):
!`git log --since="24 hours ago" --author="$(git config user.name)" --pretty='%h %s'`

Working tree:
!`git status --short`

Write a standup in three bullets: **Yesterday**, **Today** (inferred from uncommitted work,
marked as "planned"), **Blockers** (only if evident, else "none"). Maximum 60 words.
