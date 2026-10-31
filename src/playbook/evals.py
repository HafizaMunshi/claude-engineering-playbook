"""A minimal prompt-evaluation harness (course topic: "prompt evaluations").

WHAT: a ``Case`` (input + expected answer + how to grade), a ``grade`` function with
four grading strategies, ``run_eval`` to score a whole dataset, and ``compare`` to
print a leaderboard.

WHY: never judge a prompt change by eyeballing one output.  Keep a dataset,
grade every run automatically, compare pass-rates between prompt versions.

Grading strategies (``Case.grader``), cheapest and most reliable first:
  * exact    - output equals expected, ignoring case and surrounding whitespace
  * contains - expected text appears somewhere in the output
  * regex    - a regular expression (the ``expected`` field) matches the output
  * model    - another LLM ("LLM-as-judge") decides if the meaning matches; use only
               when wording varies too much for the first three.  Costs an API call
               and is itself imperfect.

HOW IT FITS: ``system_under_test`` is any ``str -> str`` callable (typically a lambda
around ``common.ask`` with the prompt being tested).  Only the ``model`` grader needs a
``client``.  Demo: ``examples/api/13_*``; tests: ``tests/test_evals_and_rag.py``.

Usage:
    cases = [Case("2+2?", "4", grader="contains")]
    report = run_eval(lambda q: ask(client, q), cases)
    print(compare({"prompt-v1": report}))
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable

from pydantic import BaseModel

from playbook.common import fast_model


@dataclass
class Case:
    """One test case in an evaluation dataset."""
    input: str                      # what is sent to the system under test
    expected: str                   # reference answer / substring / regex, per ``grader``
    grader: str = "exact"           # exact | contains | regex | model
    # ``field(default_factory=list)`` gives each Case its OWN list; a plain ``= []``
    # default would be shared between all instances (a classic Python pitfall).
    tags: list[str] = field(default_factory=list)  # free-form labels for slicing results


class Verdict(BaseModel):
    """Structured answer returned by the LLM judge."""
    correct: bool
    reason: str


def grade(case: Case, output: str, client: Any = None) -> bool:
    """Return True if ``output`` satisfies ``case`` under the case's grader.

    Args:
        case: the test case.
        output: what the system under test produced.
        client: needed ONLY for ``grader="model"``; passing None there raises
            AttributeError.
    Raises:
        ValueError: if ``case.grader`` is not one of the four known names.
        re.error: if a ``regex`` case holds an invalid pattern.
    """
    out = output.strip()
    if case.grader == "exact":
        return out.lower() == case.expected.lower()
    if case.grader == "contains":
        return case.expected.lower() in out.lower()
    if case.grader == "regex":
        # ``search`` (not ``match``) finds the pattern anywhere in the output; the
        # pattern is case-sensitive unless it carries its own (?i) flag.
        return re.search(case.expected, out) is not None
    if case.grader == "model":  # LLM-as-judge with a schema-enforced verdict
        # The cheap model is used as the judge to keep eval runs affordable.
        verdict = client.messages.parse(
            model=fast_model(), max_tokens=300, output_format=Verdict,
            messages=[{"role": "user", "content":
                       f"Reference answer:\n{case.expected}\n\nCandidate answer:\n{out}\n"
                       "Is the candidate semantically consistent with the reference?"}],
        ).parsed_output
        return verdict.correct
    raise ValueError(f"unknown grader {case.grader}")


def run_eval(system_under_test: Callable[[str], str], cases: list[Case], client: Any = None) -> dict:
    """Run every case; return pass-rate plus the failures for inspection.

    Returns a dict with keys ``total``, ``passed``, ``pass_rate`` (0.0-1.0; 0.0 for an
    empty dataset, avoiding division by zero) and ``failures`` (a list of
    ``{input, expected, got}`` so you can see WHY cases failed, not just how many).
    """
    failures = []
    for case in cases:
        output = system_under_test(case.input)
        if not grade(case, output, client):
            failures.append({"input": case.input, "expected": case.expected, "got": output})
    total = len(cases)
    return {"total": total, "passed": total - len(failures),
            "pass_rate": (total - len(failures)) / total if total else 0.0, "failures": failures}


def compare(results: dict[str, dict]) -> str:
    """Render a tiny leaderboard: prompt-version -> pass rate.

    Args:
        results: ``{label: run_eval(...) result}``.
    Returns:
        One line per label, best pass-rate first, e.g. ``v2   9/10  (90%)``.
        (``{name:<20}`` left-aligns the label in 20 columns; ``:.0%`` formats a
        fraction as a whole-number percentage.)
    """
    rows = sorted(results.items(), key=lambda kv: kv[1]["pass_rate"], reverse=True)
    return "\n".join(f"{name:<20} {r['passed']}/{r['total']}  ({r['pass_rate']:.0%})" for name, r in rows)
