#!/usr/bin/env python3
"""Concept: workflow patterns - chaining, routing, parallelization, evaluator-optimizer.

WHAT IT SHOWS
    Four ways of composing several model calls under the control of ordinary Python
    code, each run once on a small made-up input: meeting notes -> follow-up email
    (chain), a support ticket classified then answered (route), a code snippet reviewed
    from three angles at once (parallelize), and a commit message drafted, critiqued and
    refined (evaluator-optimizer).

COURSE CONCEPT (Building with the Claude API: workflows and agents)
    A WORKFLOW is a pre-defined path where your code decides the next step; an AGENT lets
    the model decide (example 04). Pick the simplest pattern that solves the problem:
      * chain             - fixed sequence, each step feeds the next (predictable, easy to debug);
      * route             - a cheap classifier picks a specialised prompt (cost + quality);
      * parallelize       - independent sub-tasks run concurrently, then are merged (latency);
      * evaluator-optimizer - generate, critique against criteria, refine (quality loops).
    Reach for a full agent only when the path cannot be known upfront.

HOW TO RUN (from the repo root)
    export ANTHROPIC_API_KEY=...        # Windows PowerShell: $env:ANTHROPIC_API_KEY="..."
    python examples/api/12_workflows.py
    Makes roughly 12-14 API calls in total, so it takes a little while and costs a few cents.

EXPECTED OUTPUT
    Four sections headed `== chain ==`, `== route ==`, `== parallelize ==` and
    `== evaluator-optimizer ==`: a short follow-up email; the parsed Ticket (category and
    urgency, likely "outage"/"high") then the first 200 characters of the specialised
    reply; a merged prioritised review (the SQL-injection issue should appear); and a
    commit message with the number of rounds it needed.

REPO MODULES USED
    playbook.workflows (chain, route, parallelize, evaluate_optimize - all the logic lives
    there and is tested offline with a fake client) and playbook.common (get_client).

GOTCHAS / TRY NEXT
    * The sample CODE contains a deliberate SQL injection (string concatenation into SQL)
      so the "security" reviewer has something to find. Never copy that pattern.
    * Workflows multiply cost and latency: every extra call is another round trip.
      Parallelization hides latency but not cost.
    * evaluate_optimize is bounded (max_rounds=3 by default) so it cannot loop forever.
    * Next: example 13 measures whether a prompt change really helps.
"""
from playbook import workflows
from playbook.common import get_client

# Sample input for the chain: names are fictional and the notes are synthetic.
NOTES = """Sync 12 Oct: Priya will finish the retry-policy PR by Friday. Dev said staging DB is flaky since
the failover test; Sam to open an infra ticket. We agreed to drop the legacy export endpoint in Q1."""
# Intentionally vulnerable code (SQL built by string concatenation) for the review demo.
CODE = 'def get_user(db, name):\n    return db.execute("SELECT * FROM users WHERE name = \'" + name + "\'").fetchall()'

if __name__ == "__main__":
    client = get_client()

    # Chain: notes -> summary -> action items -> email. We print only the final email;
    # the function also returns "summary" and "actions" if you want to inspect them.
    print("== chain ==")
    print(workflows.chain(client, NOTES)["email"])

    # Route: a small model classifies the ticket into a schema-enforced Ticket (category
    # + urgency); then a prompt specialised for that category writes the reply.
    print("\n== route ==")
    ticket, reply = workflows.route(client, "Checkout returns 500 for every user since 14:02 UTC!")
    print(ticket, "->", reply[:200])

    # Parallelize: three focused reviews (security, performance, readability) run in a
    # thread pool, then one more call merges and de-duplicates them.
    print("\n== parallelize ==")
    print(workflows.parallelize(client, CODE))

    # Evaluator-optimizer: draft a commit message, have a critic check it against the
    # criteria, and rewrite until it passes or the round limit is reached. Returns the
    # final draft and how many critique rounds were used.
    print("\n== evaluator-optimizer ==")
    draft, rounds = workflows.evaluate_optimize(
        client, "Write a commit message for: added retry with backoff to the HTTP client.",
        "Subject <= 50 chars, imperative mood, body explains why, no emoji.")
    print(f"({rounds} round(s))\n{draft}")
