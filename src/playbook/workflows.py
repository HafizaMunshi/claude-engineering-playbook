"""The four classic workflow patterns, implemented in plain Python.

WHAT: ``chain``, ``route``, ``parallelize`` and ``evaluate_optimize`` - small, readable
functions that each orchestrate several model calls in a fixed shape.

WHY: this is the "workflows vs agents" lesson of the API course.  Prefer a workflow
when the steps are known in advance: it is cheaper, faster and easier to debug than
letting a model decide what to do next.

Rule of thumb from the course: start with the simplest thing that works. These are
*workflows* (code controls the flow); an *agent* lets the model decide the flow.

  chain            - fixed sequence, each step feeds the next
  route            - classify first, then send to a specialised prompt
  parallelize      - fan out independent sub-tasks, then aggregate
  evaluate_optimize- generate, critique, refine until the critic passes

HOW IT FITS: model ids and ``text_of`` come from ``common``.  Every function takes a
``client`` first so ``tests/test_workflows.py`` can inject a fake.  The runnable demo is
``examples/api/12_*``.

Gotchas:
  * ``route`` and ``evaluate_optimize`` call ``client.messages.parse`` (structured
    outputs: the SDK validates the reply against a Pydantic model and returns it as
    ``.parsed_output``).
  * Several calls = several charges and added latency; each pattern trades cost for
    quality or speed.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Any, Literal

from pydantic import BaseModel

from playbook.common import fast_model, model as default_model, text_of


def _ask(client: Any, prompt: str, *, system: str | None = None, fast: bool = False,
         max_tokens: int = 2000) -> str:
    """Single prompt in, text out.

    Same idea as ``common.ask`` but kept private here with a ``fast`` flag name;
    ``fast=True`` selects the cheap model (used for classification / review sub-tasks).
    """
    kwargs: dict[str, Any] = dict(model=fast_model() if fast else default_model(),
                                  max_tokens=max_tokens,
                                  messages=[{"role": "user", "content": prompt}])
    if system:
        kwargs["system"] = system
    return text_of(client.messages.create(**kwargs))


# ------------------------------------------------------------------ 1. chain
def chain(client: Any, meeting_notes: str) -> dict[str, str]:
    """notes -> summary -> action items -> follow-up email. Each step sees only what it needs.

    Prompt chaining splits one big task into small focused calls.  Each call is easier
    for the model to get right, and you can inspect or test every intermediate result.
    The XML-style tags (<notes>, <summary>) clearly separate instructions from data.

    Returns:
        ``{"summary": ..., "actions": ..., "email": ...}``.
    """
    summary = _ask(client, f"Summarise these meeting notes in 5 bullets:\n<notes>\n{meeting_notes}\n</notes>")
    # Note: step 2 deliberately gets ONLY the summary, not the raw notes, to keep each
    # step's input small and its job narrow.
    actions = _ask(client, "Extract action items as `owner - task - due date (or TBD)`, one per line, "
                           f"from this summary only:\n<summary>\n{summary}\n</summary>")
    email = _ask(client, "Write a short follow-up email (under 120 words) with the summary and actions.\n"
                         f"<summary>\n{summary}\n</summary>\n<actions>\n{actions}\n</actions>")
    return {"summary": summary, "actions": actions, "email": email}


# ----------------------------------------------------------------- 2. route
class Ticket(BaseModel):
    """Schema the classifier must fill in.

    ``Literal[...]`` restricts each field to a closed set of values, so the parsed
    result can be used directly as a dictionary key (see ``HANDLERS``) with no cleanup.
    """
    category: Literal["bug", "feature_request", "question", "outage"]
    urgency: Literal["low", "medium", "high"]


# One specialised system prompt per category.  Keys must match ``Ticket.category``.
HANDLERS = {
    "bug": "You are a QA engineer. Ask for repro steps, expected vs actual, and environment.",
    "feature_request": "You are a product manager. Capture the user problem, not the proposed solution.",
    "question": "You are a support engineer. Answer concisely and link the relevant doc section.",
    "outage": "You are an incident commander. Give the first three mitigation steps and who to page.",
}


def route(client: Any, ticket_text: str) -> tuple[Ticket, str]:
    """Cheap model classifies with a schema-enforced result; a specialised prompt answers.

    Routing keeps each downstream prompt focused: instead of one giant prompt handling
    every case, a small model picks the category and the matching expert prompt runs.

    Returns:
        ``(classification, reply_text)``.
    """
    # ``output_format=Ticket`` makes the API constrain the reply to that schema;
    # ``.parsed_output`` is then a validated ``Ticket`` instance (not raw text).
    parsed = client.messages.parse(
        model=fast_model(), max_tokens=300, output_format=Ticket,
        messages=[{"role": "user", "content": f"Classify this support ticket:\n<ticket>\n{ticket_text}\n</ticket>"}],
    ).parsed_output
    reply = _ask(client, ticket_text, system=HANDLERS[parsed.category])
    return parsed, reply


# ------------------------------------------------------------- 3. parallelize
# Independent review "lenses".  Each restricts the model to one concern so findings
# do not blur together.
ASPECTS = {
    "security": "Look only for security problems (injection, secrets, authz).",
    "performance": "Look only for performance problems (N+1 queries, needless copies, blocking I/O).",
    "readability": "Look only for readability problems (naming, size, duplication).",
}


def parallelize(client: Any, code: str, aspects: dict[str, str] | None = None, max_workers: int = 3) -> str:
    """Independent reviews run concurrently, then one call merges them.

    Args:
        client: Anthropic client; must be safe to share between threads (the real SDK
            client is).
        code: the source text to review.
        aspects: ``{name: instruction}``; defaults to ``ASPECTS``.
        max_workers: how many API calls may be in flight at once.
    Returns:
        One merged, prioritised review.
    """
    aspects = aspects or ASPECTS

    def review(item: tuple[str, str]) -> tuple[str, str]:
        name, instruction = item
        return name, _ask(client, f"{instruction} Max 3 findings, one line each.\n<code>\n{code}\n</code>", fast=True)

    # The work is network-bound (waiting on the API), so threads give a real speed-up
    # despite Python's GIL.  ``pool.map`` keeps results in the SAME ORDER as the input.
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        reviews = list(pool.map(review, aspects.items()))
    merged = "\n".join(f"## {name}\n{text}" for name, text in reviews)
    # Aggregation step uses the stronger model: it must weigh and de-duplicate findings.
    return _ask(client, f"Merge these reviews into one prioritised list, removing duplicates:\n{merged}")


# --------------------------------------------------- 4. evaluator-optimizer
class Critique(BaseModel):
    """The critic's structured verdict: did the draft pass, and if not, why not."""
    passes: bool
    feedback: str


def evaluate_optimize(client: Any, task: str, criteria: str, max_rounds: int = 3) -> tuple[str, int]:
    """Generate -> critique -> refine. Returns (final draft, rounds used).

    A cheap critic model checks the draft against ``criteria``; if it fails, its
    feedback is fed to a rewrite call.  ``max_rounds`` bounds cost and prevents an
    endless loop with a critic that is never satisfied.

    Returns:
        ``(draft, rounds)`` where ``rounds`` is the round on which the critic passed,
        or ``max_rounds`` if it never did (the last rewrite is returned UNCHECKED).
    """
    draft = _ask(client, task)
    for round_no in range(1, max_rounds + 1):
        critique = client.messages.parse(
            model=fast_model(), max_tokens=500, output_format=Critique,
            messages=[{"role": "user", "content":
                       f"Criteria:\n{criteria}\n\nDraft:\n<draft>\n{draft}\n</draft>\n"
                       "Does the draft meet ALL criteria? Give specific feedback if not."}],
        ).parsed_output
        if critique.passes:
            return draft, round_no
        draft = _ask(client, f"Task: {task}\n\nPrevious draft:\n{draft}\n\nFix these issues:\n{critique.feedback}")
    return draft, max_rounds
