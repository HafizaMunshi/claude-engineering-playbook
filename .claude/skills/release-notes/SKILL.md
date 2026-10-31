---
name: release-notes
description: Use when asked to draft release notes or a changelog entry from git history between two tags or refs. Groups changes for readers, not committers.
---

# Release notes

## Procedure
1. Determine the range (`<prev-tag>..<tag>`); if missing, use `git describe --tags --abbrev=0` for the previous tag.
2. Collect: `git log --no-merges --pretty='%h %s' <range>` and, for unclear subjects, `git show --stat <hash>`.
3. Drop noise: formatting, dependency churn without user impact, reverts that cancel out.
4. Group under: **Added**, **Changed**, **Fixed**, **Security**, **Breaking changes** (put first if non-empty).
5. Rewrite each line as user-visible impact in plain words; keep the short hash in parentheses for traceability.
6. End with **Upgrade notes** for migrations, config changes, or removed endpoints.

## Rules
- Do not invent features from commit titles you did not verify.
- Breaking changes must say what to do instead.
- Keep each bullet to one line.
