#!/usr/bin/env python3
"""Concept: production hygiene - typed errors, SDK retries, token counting before you spend.

The SDK already retries 408/409/429/5xx with backoff (max_retries, default 2). Catch a
most-specific-first chain, never one broad `except Exception`, so retryable and
non-retryable failures are handled differently.

WHAT IT SHOWS
    `safe_call` wraps a request in a specific-to-general chain of exception handlers and
    returns a readable string for each failure mode. `estimate_input_cost` counts the
    tokens of a prompt with the free token-counting endpoint and converts them to dollars
    BEFORE any money is spent.

COURSE CONCEPT (Building with the Claude API: production concerns)
    Failures differ and deserve different responses:
      * 400 BadRequestError    - your request is wrong; retrying cannot help, fix the code;
      * 401 AuthenticationError - bad or missing key;
      * 429 RateLimitError     - slow down; the response has a `retry-after` header;
      * other APIStatusError   - 5xx etc.; the `request-id` header is what support needs;
      * APIConnectionError     - network trouble before a response arrived.
    Python picks the FIRST matching except clause, so subclasses must be listed before
    their parents (all the status errors inherit from APIStatusError). Separately, an HTTP
    200 can still mean "no answer": stop_reason "refusal" must be checked before you read
    `content`. Cost control: count tokens first, cap max_tokens, and cache big prefixes.

HOW TO RUN (from the repo root)
    export ANTHROPIC_API_KEY=...        # Windows PowerShell: $env:ANTHROPIC_API_KEY="..."
    python examples/api/15_errors_and_cost.py
    Try an invalid key to see the auth branch: ANTHROPIC_API_KEY=bad python ...

EXPECTED OUTPUT
    `estimated input cost: $0.0xxx` (a few thousand tokens at the assumed price), then the
    model's reply to "Say hello in one word." (or an error string such as `auth failed...`).

REPO MODULES USED
    playbook.common: get_client(), model().

GOTCHAS / TRY NEXT
    * The default rate of 4.0 USD per million input tokens is an ASSUMPTION for the demo,
      not a live price list; pass your model's real price. Output tokens and cache
      pricing are not included, so treat the figure as a lower bound.
    * `with_options(...)` returns a COPY of the client with different settings; the
      original client is unchanged.
    * The SDK has already retried before RateLimitError / APIStatusError reach you.
    * Next steps: add logging of request ids, and a spend budget per run.
"""
import anthropic

from playbook.common import get_client, model


def safe_call(client: anthropic.Anthropic, prompt: str) -> str:
    """Send one prompt and turn every failure mode into a readable string.

    Args:
        client: an `anthropic.Anthropic` instance.
        prompt: the user prompt to send.

    Returns:
        The reply text on success, or a short description of what went wrong.
    """
    try:
        # with_options: per-call overrides on a copy of the client.
        #   max_retries=4 - the SDK retries 408/409/429/5xx and connection errors with
        #                   exponential backoff (default is 2) before raising.
        #   timeout=60.0  - give up if the request takes longer than 60 seconds.
        r = client.with_options(max_retries=4, timeout=60.0).messages.create(
            model=model(), max_tokens=500, messages=[{"role": "user", "content": prompt}])
    except anthropic.BadRequestError as e:          # our bug: fix the request, don't retry
        return f"bad request: {e.message}"
    except anthropic.AuthenticationError:
        return "auth failed: check ANTHROPIC_API_KEY"
    except anthropic.RateLimitError as e:           # SDK retries already exhausted
        # retry-after: how many seconds the server asks you to wait ("?" if absent).
        return f"rate limited; retry-after={e.response.headers.get('retry-after', '?')}s"
    except anthropic.APIStatusError as e:
        # Catch-all for the remaining HTTP error statuses (e.g. 500, 529 overloaded).
        # It must come AFTER the specific classes above because they are its subclasses.
        # request-id identifies this call to Anthropic support.
        return f"server-side problem ({e.status_code}); request-id={e.response.headers.get('request-id')}"
    except anthropic.APIConnectionError:
        # No HTTP response at all (DNS, TCP, TLS or timeout). Not an APIStatusError.
        return "network error"
    # HTTP 200 but the model declined: check stop_reason before reading content.
    if r.stop_reason == "refusal":
        # stop_details carries extra information about why the model declined.
        return f"refused: {r.stop_details}"
    # Concatenate all text blocks; other block types (thinking, tool_use) are skipped.
    return "".join(b.text for b in r.content if b.type == "text")


def estimate_input_cost(client, prompt: str, usd_per_mtok: float = 4.0) -> float:
    """Count tokens BEFORE sending (free endpoint) and turn them into dollars.

    Args:
        client: an `anthropic.Anthropic` instance.
        prompt: the user prompt whose input size you want to price.
        usd_per_mtok: assumed price in US dollars per million input tokens.

    Returns:
        Estimated input cost in US dollars (input tokens only).
    """
    # count_tokens takes the same model/messages as a real call but generates nothing, so
    # it costs no tokens (it is rate limited though). input_tokens is the exact size the
    # real request would be billed for on the input side.
    tokens = client.messages.count_tokens(model=model(), messages=[{"role": "user", "content": prompt}]).input_tokens
    return tokens * usd_per_mtok / 1_000_000


if __name__ == "__main__":
    c = get_client()
    # A deliberately large prompt (about 4,000 words of filler) to show a non-trivial cost.
    big_prompt = "Summarise: " + "lorem ipsum " * 2000
    print(f"estimated input cost: ${estimate_input_cost(c, big_prompt):.4f}")
    print(safe_call(c, "Say hello in one word."))
