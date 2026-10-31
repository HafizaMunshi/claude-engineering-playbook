#!/usr/bin/env python3
"""Concept: streaming - show tokens as they arrive, then fetch the complete message.

WHAT IT SHOWS
    One request made with `messages.stream` instead of `messages.create`. Text is
    printed the moment the model produces it, and afterwards the complete Message
    object (with usage and stop_reason) is retrieved from the same stream.

COURSE CONCEPT (Building with the Claude API: streaming)
    Without streaming, the HTTP call blocks until the whole answer is finished, which
    can be many seconds for long outputs. Streaming gives a fast "time to first token"
    (good for chat UIs and CLIs) and avoids HTTP timeouts on long generations (the SDK
    even refuses non-streaming calls when max_tokens is large enough that the request
    could outlast a normal timeout). Token cost is identical either way.

HOW TO RUN (from the repo root)
    export ANTHROPIC_API_KEY=...        # Windows PowerShell: $env:ANTHROPIC_API_KEY="..."
    python examples/api/02_streaming.py

EXPECTED OUTPUT
    Six bullets about idempotency keys appearing progressively in the terminal,
    followed by a blank line and `stop_reason=end_turn output_tokens=<n>`.

REPO MODULES USED
    playbook.common: get_client(), model().

GOTCHAS / TRY NEXT
    * `text_stream` yields only text deltas. For tool calls or thinking you iterate
      the raw events instead (`for event in stream`).
    * `flush=True` matters: stdout is line-buffered, so without it text may appear
      in lumps instead of smoothly.
    * Check `stop_reason`: "max_tokens" would mean the answer was truncated.
    * Next: example 03 makes the model return validated JSON instead of prose.
"""
from playbook.common import get_client, model

if __name__ == "__main__":
    client = get_client()
    # `messages.stream` is a context manager: leaving the `with` block closes the
    # HTTP connection cleanly even if an exception is raised mid-stream.
    with client.messages.stream(
        # max_tokens is the output cap. It is set generously because streaming is
        # the safe way to allow long outputs; the model stops by itself when done.
        model=model(), max_tokens=3000,
        messages=[{"role": "user", "content": "Explain idempotency keys for payment APIs in 6 bullets."}],
    ) as stream:
        # text_stream yields small string fragments (text deltas) as they arrive.
        for chunk in stream.text_stream:
            print(chunk, end="", flush=True)
        # Once the stream is exhausted, this assembles everything into the same Message
        # object that `messages.create` would have returned.
        final = stream.get_final_message()  # full Message with usage + stop_reason
    # stop_reason says WHY generation stopped: "end_turn" = finished naturally,
    # "max_tokens" = hit the cap, "tool_use" = wants a tool, "refusal" = declined.
    # usage.output_tokens is the number of tokens generated (what output billing uses).
    print(f"\n\nstop_reason={final.stop_reason} output_tokens={final.usage.output_tokens}")
