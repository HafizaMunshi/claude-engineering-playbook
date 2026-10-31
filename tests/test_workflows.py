"""Tests for playbook.workflows - the four classic LLM workflow patterns, with a fake client.

Patterns: chain, route, parallelize, evaluate_optimize. In each, CODE controls the flow
(unlike an agent, where the model decides), so the tests assert on the flow itself: what was
sent to the model at each step and how many calls were made. Replies are scripted with
FakeClient (see conftest.py).

Run: .venv\\Scripts\\python.exe -m pytest tests/test_workflows.py -q
"""
from playbook import workflows
from playbook.workflows import Critique, Ticket


def test_chain_passes_each_output_to_next_step(fake):
    """Step N's output is embedded in step N+1's prompt (summary -> actions -> email).

    Guards the defining property of a chain. If a step used the raw notes instead of the
    previous output, SUMMARY/ACTIONS would be missing from the later prompts.
    """
    client = fake(create=["SUMMARY", "ACTIONS", "EMAIL"])
    result = workflows.chain(client, "notes")
    assert result == {"summary": "SUMMARY", "actions": "ACTIONS", "email": "EMAIL"}
    calls = client.messages.create_calls
    assert "SUMMARY" in calls[1]["messages"][0]["content"]
    assert "ACTIONS" in calls[2]["messages"][0]["content"]


def test_route_uses_category_specific_system_prompt(fake):
    """The classifier's category selects the specialised system prompt for the answer.

    parse=[...] scripts the structured classification (outage/high); create_calls[0] is the
    answering call, whose system prompt must be the incident-commander one. Fails if routing
    uses the wrong handler or ignores the category.
    """
    client = fake(create=["Page the on-call."], parse=[Ticket(category="outage", urgency="high")])
    ticket, reply = workflows.route(client, "site is down")
    assert ticket.category == "outage" and reply == "Page the on-call."
    assert "incident commander" in client.messages.create_calls[0]["system"]


def test_parallelize_makes_one_call_per_aspect_plus_merge(fake):
    """N independent reviews (one per aspect) then exactly one merge call.

    Uses a CALLABLE responder because the reviews run in threads, so call order is not
    deterministic; the reply is chosen by looking at the prompt ("Merge" marks the final
    call). Fails if an aspect is skipped, duplicated, or the merge step disappears.
    """
    client = fake(create=lambda kw: "merged" if "Merge" in kw["messages"][0]["content"] else "finding")
    assert workflows.parallelize(client, "code") == "merged"
    assert len(client.messages.create_calls) == len(workflows.ASPECTS) + 1


def test_evaluate_optimize_stops_when_critic_passes(fake):
    """Round 1 fails (feedback -> redraft), round 2 passes -> returns draft2 after 2 rounds.

    Protects the early exit: the loop must stop as soon as the critic approves rather than
    always running max_rounds (wasted cost), and must return the revised draft.
    """
    client = fake(create=["draft1", "draft2"],
                  parse=[Critique(passes=False, feedback="too long"), Critique(passes=True, feedback="")])
    draft, rounds = workflows.evaluate_optimize(client, "task", "criteria")
    assert (draft, rounds) == ("draft2", 2)


def test_evaluate_optimize_gives_up_after_max_rounds(fake):
    """A critic that never passes must not loop forever: stop at max_rounds (3).

    Scripted with 3 failing critiques and 4 drafts (initial + 3 revisions). Fails if the
    loop is unbounded or miscounts rounds.
    """
    bad = Critique(passes=False, feedback="no")
    client = fake(create=["d1", "d2", "d3", "d4"], parse=[bad, bad, bad])
    _, rounds = workflows.evaluate_optimize(client, "t", "c", max_rounds=3)
    assert rounds == 3
