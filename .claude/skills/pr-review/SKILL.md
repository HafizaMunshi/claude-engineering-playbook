---
name: pr-review
description: Use when asked to review a pull request, a branch diff, or staged changes. Produces a severity-ranked review covering correctness, security, tests and maintainability.
---

# PR review

## Procedure
1. Get the diff: `git diff --stat <base>...HEAD`, then read changed files in full, not just hunks.
2. Restate the intent of the change in one sentence. If you cannot, say so - that is finding #1.
3. Walk the checklist in order and stop to verify any suspicion by reading the code (never guess):
   - **Correctness**: edge cases (null/empty/large), off-by-one, error paths, concurrency, idempotency of retries.
   - **Security**: untrusted input reaching SQL, shell, URLs, file paths or deserialisers; secrets in code or logs; authz checks on new endpoints.
   - **Data/contracts**: backwards compatibility of API shapes, migrations that are not append-only, nullable-to-required changes.
   - **Tests**: does a test fail without this change? Are error paths covered? Any mocks hiding the real behaviour?
   - **Maintainability**: naming, dead code, duplicated logic, comments that explain *why*.
4. Rank findings and cap at the 10 that matter most.

## Output format
```
Summary: <1-2 sentences, verdict: approve / approve with nits / request changes>

[blocker] path/file.py:42 - <problem>. Why it matters: <impact>. Suggestion: <fix>.
[major]   ...
[nit]     ...
Questions: <only genuine open questions>
```

## Rules
- Cite `file:line` for every finding. No finding without evidence.
- Do not restate what the diff already shows. Do not pad with praise.
- Do not edit files during a review unless the user asks for fixes.
