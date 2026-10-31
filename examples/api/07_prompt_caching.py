#!/usr/bin/env python3
"""Concept: prompt caching - pay full price for a big shared prefix once, ~10% afterwards.

WHAT IT SHOWS
    The same large "handbook" is sent as the system prompt with two different questions.
    The first call WRITES the handbook into the cache; the second call READS it, and the
    printed usage numbers prove it.

COURSE CONCEPT (Building with the Claude API: prompt caching)
    Re-sending a big, unchanging prefix (style guide, API spec, codebase map, tool
    definitions) on every call is slow and expensive. Mark the end of that prefix with
    `cache_control` and the API stores it for a short time (the default "ephemeral" cache
    lives a few minutes and is refreshed on each hit). Reads cost roughly 10% of normal
    input price and are faster; the first write costs a bit MORE than normal input. So
    caching pays off when the same prefix is reused several times in a short window.
    Caching is a PREFIX match: keep stable content (instructions, reference docs) first
    and put anything volatile (timestamps, the user's question) after it, or the cache
    never hits.

HOW TO RUN (from the repo root)
    export ANTHROPIC_API_KEY=...        # Windows PowerShell: $env:ANTHROPIC_API_KEY="..."
    python examples/api/07_prompt_caching.py

EXPECTED OUTPUT
    Two lines of the form `written=N read=M uncached=K -> '<first 80 chars of answer>'`.
    Expect line 1: written large, read 0. Line 2: written 0, read large (same number).
    `uncached` is the small non-cached remainder (the question itself).

REPO MODULES USED
    playbook.common: get_client(), model(), text_of().

GOTCHAS / TRY NEXT
    * Verify with usage.cache_read_input_tokens - zero on call 2 means something upstream
      of the cache marker keeps changing (or the prefix is below the minimum length, or
      the cache expired).
    * The prefix must exceed the model's minimum cacheable length; shorter prefixes are
      silently not cached (both counters stay 0).
    * Run the script twice within a few minutes: then even call 1 will show a read.
    * Next: example 08 shows the thinking and effort controls.
"""
from playbook.common import get_client, model, text_of

# Must exceed the model's minimum cacheable length to be cached.
# Real use: style guide, API spec, codebase map.
# The sentence is repeated 400 times purely to make the text long enough; the content is filler.
HANDBOOK = ("Engineering handbook. " + "Services must expose /health and /metrics. " * 400)


def ask_with_cache(client, question: str):
    """Ask a question against the cached handbook.

    Args:
        client: an `anthropic.Anthropic` instance (injectable for tests).
        question: the volatile part of the request (changes every call).

    Returns:
        The full Message response (not just text) so the caller can read `usage`.
    """
    return client.messages.create(
        model=model(), max_tokens=500,
        # `system` can be a list of text blocks instead of a string; that form is what
        # lets you attach per-block options such as cache_control.
        # cache_control {"type": "ephemeral"} = "cache everything up to and including
        # this block". Everything before this marker must be identical on later calls.
        system=[{"type": "text", "text": HANDBOOK, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": question}],   # volatile part AFTER the cached prefix
    )


if __name__ == "__main__":
    client = get_client()
    for q in ("Which endpoints must a service expose?", "And which one is for scraping by monitoring?"):
        r = ask_with_cache(client, q)
        u = r.usage
        # usage fields:
        #   cache_creation_input_tokens - tokens written to the cache (billed at a premium);
        #   cache_read_input_tokens     - tokens served from the cache (billed at a discount);
        #   input_tokens                - ordinary uncached input after the last cache marker.
        print(f"written={u.cache_creation_input_tokens} read={u.cache_read_input_tokens} "
              f"uncached={u.input_tokens} -> {text_of(r)[:80]!r}")
