#!/usr/bin/env python3
"""Concept: prompt evaluation - measure, don't guess.

WHAT IT SHOWS
    Two versions of a prompt that classifies bug severity (a vague one and one with a
    rubric) are run over the same six labelled cases. The script prints a leaderboard of
    pass rates and up to two failing cases per prompt.

COURSE CONCEPT (Building with the Claude API: prompt evaluations)
    Never judge a prompt change by eyeballing one output. Keep a dataset of inputs with
    expected answers, grade every run automatically, and compare pass rates between prompt
    versions. This turns "it feels better" into a number you can track in CI and use to
    catch regressions when you change the prompt or switch models.

HOW TO RUN (from the repo root)
    export ANTHROPIC_API_KEY=...        # Windows PowerShell: $env:ANTHROPIC_API_KEY="..."
    python examples/api/13_prompt_evals.py
    Makes 12 small calls (6 cases x 2 prompts) with the fast model, so it is cheap.

EXPECTED OUTPUT
    A leaderboard with one line per prompt, best first, such as `v2-rubric  6/6  (100%)`
    and `v1-vague  2/6  (33%)`, followed by lines `<name> failed: {...}` for failing
    cases. The vague prompt usually scores lower because the model replies with a sentence
    ("This is a high severity issue...") and the grader uses an exact match on one word.
    Exact numbers vary.

REPO MODULES USED
    playbook.evals: Case (a labelled example), run_eval (runs and grades), compare (renders
    the leaderboard). playbook.common: ask (one-shot prompt helper), fast_model (imported
    but unused here), get_client.

GOTCHAS / TRY NEXT
    * Cases here use the default "exact" grader (case-insensitive equality). Other graders
      are "contains", "regex" and "model" (an LLM judge); see playbook.evals.
    * Six cases is a toy dataset. Real evals need dozens to hundreds of cases, including
      tricky edge cases, or the pass rate is noise.
    * Because outputs are not deterministic, re-run before trusting a small difference.
    * Next: example 14 uses tools that Anthropic runs for you.
"""
from playbook.common import ask, fast_model, get_client
from playbook.evals import Case, compare, run_eval

# The labelled dataset: Case(input, expected_output). Severity words are the ground truth.
CASES = [
    Case("Users cannot log in at all", "high"),
    Case("Typo on the pricing page", "low"),
    Case("Export is slow for large files", "medium"),
    Case("Payments failing for every customer", "high"),
    Case("Button colour slightly off in dark mode", "low"),
    Case("Search occasionally returns stale results", "medium"),
]

# Version 1: a vague instruction with no definitions and no output-format constraint.
PROMPT_V1 = "What is the severity (low/medium/high) of this issue? {issue}"
# Version 2: defines each level (a rubric) and demands a one-word lowercase reply, which
# makes the output easy to grade with an exact match.
PROMPT_V2 = ("Classify issue severity. high = users blocked or money lost; medium = degraded but workaround exists; "
             "low = cosmetic. Reply with ONE lowercase word only.\nIssue: {issue}")

if __name__ == "__main__":
    client = get_client()
    # Build {prompt name: eval result}. The lambda is the "system under test": it takes
    # one issue string and returns the model's answer. `p=prompt` binds the CURRENT prompt
    # at definition time (otherwise every lambda would see the last loop value).
    # max_tokens=20 caps the reply (a one-word answer needs few tokens and a long
    # rambling reply is simply a failure); use_fast=True picks the cheap model.
    results = {
        name: run_eval(lambda issue, p=prompt: ask(client, p.format(issue=issue), max_tokens=20, use_fast=True),
                       CASES, client)
        for name, prompt in {"v1-vague": PROMPT_V1, "v2-rubric": PROMPT_V2}.items()
    }
    print(compare(results))
    # Show at most two failures per prompt to see WHY it failed (input, expected, got).
    for name, r in results.items():
        for f in r["failures"][:2]:
            print(f"  {name} failed: {f}")
