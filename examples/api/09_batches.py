#!/usr/bin/env python3
"""Concept: Message Batches - 50% cheaper asynchronous processing for non-urgent bulk work.

WHAT IT SHOWS
    Four commit messages are submitted as ONE batch of four independent requests, the
    script polls until the batch has finished, then prints each label keyed by custom_id.

COURSE CONCEPT (Building with the Claude API: batch processing)
    A batch trades latency for price: requests are processed asynchronously (usually
    within an hour, can take up to 24h) at about half the normal token price. Good for:
    nightly classification, backfills, eval runs. Not good for anything a user is waiting
    on. Results come back in ANY order, so always key by custom_id, never by position.

HOW TO RUN (from the repo root)
    export ANTHROPIC_API_KEY=...        # Windows PowerShell: $env:ANTHROPIC_API_KEY="..."
    python examples/api/09_batches.py
    Be patient: it polls every 10 seconds and may take minutes. It blocks until done.

EXPECTED OUTPUT
    `submitted <batch id>` then, once finished, four lines sorted by id:
    `commit-0 -> bug`, `commit-1 -> feature`, `commit-2 -> chore`, `commit-3 -> bug`
    (labels may vary slightly, e.g. extra punctuation, since output is free text).

REPO MODULES USED
    playbook.common: fast_model() (cheap model for a simple label task), get_client().

GOTCHAS / TRY NEXT
    * Each request has its own `params`, exactly like a normal messages.create body.
    * A request can fail individually (errored / canceled / expired) while others
      succeed; `collect` records the failure type instead of crashing.
    * The script does not time out: if a batch hangs, Ctrl+C and look the batch id up
      in the Console. Results are kept for a limited time after the batch ends.
    * Combine with prompt caching (example 07) for a shared prefix to save even more.
    * Next: example 10 returns answers with citations.
"""
import time

from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
from anthropic.types.messages.batch_create_params import Request

from playbook.common import fast_model, get_client

COMMITS = ["fix: handle null customer id", "feat: add csv export", "chore: bump deps", "fix: race in job scheduler"]


def submit(client, commits: list[str]):
    """Create a batch with one classification request per commit message.

    Args:
        client: an `anthropic.Anthropic` instance (injectable for tests).
        commits: commit message strings to label.

    Returns:
        The batch object; its `.id` is needed to poll and fetch results. Creating the
        batch returns immediately - nothing has been processed yet.
    """
    return client.messages.batches.create(requests=[
        # custom_id: YOUR identifier for the request (unique within the batch). It is the
        # only reliable way to match a result to its input because order is not guaranteed.
        # params: the same fields as a normal non-streaming messages.create call.
        Request(custom_id=f"commit-{i}", params=MessageCreateParamsNonStreaming(
            # max_tokens=50: the answer is one word, so a tiny cap keeps cost down.
            model=fast_model(), max_tokens=50,
            messages=[{"role": "user", "content": f"Label as exactly one of bug|feature|chore: {c}"}]))
        for i, c in enumerate(commits)
    ])


def collect(client, batch_id: str, poll_seconds: int = 10) -> dict[str, str]:
    """Wait for a batch to end and return {custom_id: label text}.

    Args:
        client: an `anthropic.Anthropic` instance.
        batch_id: id returned by `submit`.
        poll_seconds: pause between status checks (sleeping avoids hammering the API).

    Returns:
        Mapping from custom_id to the answer text, or `<result type>` such as
        `<errored>` for requests that did not succeed.
    """
    # processing_status is "in_progress" until every request has finished, then "ended"
    # (ended does NOT mean every request succeeded; check each result).
    while client.messages.batches.retrieve(batch_id).processing_status != "ended":
        time.sleep(poll_seconds)
    out = {}
    # results() streams one item per request, in arbitrary order.
    for item in client.messages.batches.results(batch_id):
        # result.type is one of: succeeded, errored, canceled, expired.
        if item.result.type == "succeeded":
            # On success, result.message is a normal Message; take its first text block.
            out[item.custom_id] = next(b.text for b in item.result.message.content if b.type == "text")
        else:
            out[item.custom_id] = f"<{item.result.type}>"
    return out


if __name__ == "__main__":
    client = get_client()
    batch = submit(client, COMMITS)
    print("submitted", batch.id)
    # sorted() gives stable output; "commit-10" would sort before "commit-2" as text,
    # which is fine for 4 items but worth knowing for larger batches.
    for cid, label in sorted(collect(client, batch.id).items()):
        print(cid, "->", label)
