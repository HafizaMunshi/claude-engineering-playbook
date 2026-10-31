#!/usr/bin/env python3
"""Concept: server-side tools - Anthropic runs them, you just declare them.

* code_execution - Claude writes and runs code in a sandbox (exact maths, data wrangling)
* web_search     - live web results with citations
No tool loop on your side; results arrive as extra content blocks in the same response.

WHAT IT SHOWS
    Two requests: one asks Claude to compute percentiles of a list of numbers (it writes
    and runs code in Anthropic's sandbox), the other asks a current-events question that
    needs a live web search.

COURSE CONCEPT (Building with the Claude API: tool use, server tools)
    With the client-side tools of examples 04/05 YOU execute the function and send back a
    result. Server tools are executed by Anthropic inside the same API request, so there
    is no loop to write: you declare the tool and read the finished response. Use
    code_execution when precision matters (LLMs are poor at exact arithmetic) and
    web_search when the answer is newer than the model's training data. Cost note: both
    add extra tokens and tool charges; `max_uses` caps web searches per request.

HOW TO RUN (from the repo root)
    export ANTHROPIC_API_KEY=...        # Windows PowerShell: $env:ANTHROPIC_API_KEY="..."
    python examples/api/14_server_tools.py
    Both tools must be enabled for your organisation, or the API returns an error.

EXPECTED OUTPUT
    Explanatory text with the p50/p95/p99 values, a `[sandbox stdout] ...` line with the
    raw program output, then a short cited summary about the latest stable Python release.

REPO MODULES USED
    playbook.common: get_client(), model().

GOTCHAS / TRY NEXT
    * Tool `type` strings are dated versions (e.g. a "20260120" suffix); older or newer
      versions may be required as the API evolves - check the API docs if you get a
      validation error.
    * The sandbox has no access to your files or network; treat it as a calculator.
    * Server tools may return stop_reason "pause_turn" for long-running work; the caller
      then re-sends the conversation to let it continue. This demo does not handle that.
    * Web search results come back as extra content blocks; the final text carries the
      citations. The script prints only the first text block.
    * Next: example 15 covers errors and cost control.
"""
from playbook.common import get_client, model


def run_code(client, task: str):
    """Ask Claude to solve a task by writing and executing code in a sandbox.

    Args:
        client: an `anthropic.Anthropic` instance (injectable for tests).
        task: the problem to solve, e.g. a calculation over data in the prompt.

    Returns:
        The full Message, whose content mixes text blocks with tool-call and
        tool-result blocks from the sandbox.
    """
    return client.messages.create(
        model=model(), max_tokens=4000,
        # `tools` for a server tool is a type + name declaration only; there is no
        # input_schema or handler because you never run it. The versioned `type` selects
        # the code-execution tool; `name` is how the model refers to it.
        tools=[{"type": "code_execution_20260120", "name": "code_execution"}],
        messages=[{"role": "user", "content": task}],
    )


def web_search(client, question: str):
    """Ask a question that needs fresh information from the web.

    Args:
        client: an `anthropic.Anthropic` instance (injectable for tests).
        question: the question to research.

    Returns:
        The full Message; text blocks carry citations to the pages used.
    """
    return client.messages.create(
        model=model(), max_tokens=3000,
        # max_uses=3: the model may search at most three times for this request. This
        # bounds both cost and latency (each search adds results to the input tokens).
        tools=[{"type": "web_search_20260209", "name": "web_search", "max_uses": 3}],
        messages=[{"role": "user", "content": question}],
    )


if __name__ == "__main__":
    client = get_client()
    r = run_code(client, "Compute the p50, p95 and p99 of [12, 15, 11, 90, 14, 13, 16, 120, 12, 14].")
    # Walk the content blocks in order. Types you can meet:
    #   text                              - prose from the model;
    #   server_tool_use                   - the model's call to the sandbox (the code it ran);
    #   bash_code_execution_tool_result   - what the sandbox printed (stdout/stderr/return code).
    for b in r.content:
        if b.type == "text":
            print(b.text)
        elif b.type == "bash_code_execution_tool_result" and b.content.type == "bash_code_execution_result":
            # The inner result object holds stdout; an error variant would not have it,
            # hence the second type check.
            print("[sandbox stdout]", b.content.stdout.strip())

    r = web_search(client, "What changed in the latest stable Python release? Cite sources.")
    # The response interleaves server_tool_use / web_search_tool_result blocks with text;
    # take the first text block (default "" if there is none).
    print(next((b.text for b in r.content if b.type == "text"), ""))
