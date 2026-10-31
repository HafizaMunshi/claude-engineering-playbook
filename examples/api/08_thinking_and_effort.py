#!/usr/bin/env python3
"""Concept: extended (adaptive) thinking + the effort dial.

WHAT IT SHOWS
    The same reasoning puzzle (rank latency fixes by expected p99 gain) is sent twice,
    once with effort "low" and once with "high", and the script prints how many output
    tokens and how many characters of reasoning summary each run produced.

COURSE CONCEPT (Building with the Claude API: extended thinking)
    Adaptive thinking lets the model decide how much to reason before answering. `effort`
    trades quality for cost/latency: low for routing/classification, medium/high for most
    work, xhigh/max for hard problems. Thinking tokens are billed as OUTPUT tokens, so
    higher effort means a bigger bill and a slower answer; use the lowest effort that
    still gives acceptable quality. `display: summarized` makes the reasoning summary
    visible (default is omitted). This replaces the older fixed "thinking budget" style
    and avoids sampling parameters such as temperature, which current models reject.

HOW TO RUN (from the repo root)
    export ANTHROPIC_API_KEY=...        # Windows PowerShell: $env:ANTHROPIC_API_KEY="..."
    python examples/api/08_thinking_and_effort.py

EXPECTED OUTPUT
    Two sections, `--- effort=low: ...` and `--- effort=high: ...`, each with the
    output_tokens count, the reasoning-summary character count and the first 400
    characters of the answer. Expect "high" to use noticeably more tokens; exact numbers
    vary, and "low" may produce a very short (or even empty) summary.

REPO MODULES USED
    playbook.common: get_client(), model().

GOTCHAS / TRY NEXT
    * Content blocks come back in order: "thinking" block(s) first, then "text". Never
      assume content[0] is the answer; select by type as done below.
    * The summary is a condensed version of the reasoning, not the raw chain of thought,
      and you are billed for the full thinking, not the summary.
    * max_tokens must leave room for thinking AND the answer; 8000 is generous here.
    * `next(...)` below raises StopIteration if no text block exists (for instance when
      max_tokens is exhausted during thinking), so check stop_reason in real code.
    * Try effort "medium" or "max" and compare cost against answer quality.
    * Next: example 09 processes many requests cheaply in a batch.
"""
from playbook.common import get_client, model

PUZZLE = ("A service has p99 latency 800ms. Profiling shows 60% in DB calls (40% of those are N+1), "
          "20% in JSON serialisation, 20% elsewhere. Rank three fixes by expected p99 gain and justify.")

if __name__ == "__main__":
    client = get_client()
    for effort in ("low", "high"):
        r = client.messages.create(
            model=model(), max_tokens=8000,
            # thinking {"type": "adaptive"}: the model chooses whether and how long to
            # think, rather than you fixing a token budget.
            # "display": "summarized": return a human-readable summary of the reasoning
            # in `thinking` blocks (the default omits it, you would only see the answer).
            thinking={"type": "adaptive", "display": "summarized"},
            # output_config.effort: how hard the model tries overall (thinking depth and
            # answer thoroughness). It is the supported replacement for temperature-style
            # tuning in this repo.
            output_config={"effort": effort},
            messages=[{"role": "user", "content": PUZZLE}],
        )
        # A "thinking" content block exposes `.thinking` (the summary text). Sum its length
        # over all thinking blocks; blocks of other types are skipped.
        thinking = sum(len(b.thinking) for b in r.content if b.type == "thinking")
        # The "text" block holds the final answer for the user.
        answer = next(b.text for b in r.content if b.type == "text")
        # usage.output_tokens includes the thinking tokens, which is the cost signal here.
        print(f"--- effort={effort}: output_tokens={r.usage.output_tokens}, reasoning-summary chars={thinking}")
        print(answer[:400], "...\n")
