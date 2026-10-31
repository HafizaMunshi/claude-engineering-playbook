#!/usr/bin/env python3
"""Concept: the SDK tool runner - same agent as example 04, but the loop is the SDK's job.

WHAT IT SHOWS
    Two ordinary Python functions (`git_log`, `count_lines`) are turned into tools with
    the `@beta_tool` decorator and handed to `tool_runner`, which calls the model, runs
    the requested functions, sends results back and repeats until the model is done.

COURSE CONCEPT (Building with the Claude API: tool use, SDK helpers)
    Example 04 wrote the loop by hand to show the protocol. In production you usually let
    the SDK do it. `@beta_tool` builds each tool's JSON schema from the function's type
    hints and its docstring (the summary becomes the tool description, the `Args:` section
    becomes parameter descriptions), so the schema cannot drift from the code. That is why
    the docstrings below are functional, not just documentation: the model reads them.

HOW TO RUN (from the repo root, which must be a git repo with a README.md)
    export ANTHROPIC_API_KEY=...        # Windows PowerShell: $env:ANTHROPIC_API_KEY="..."
    python examples/api/05_tool_runner.py
    Requires the `git` executable on PATH.

EXPECTED OUTPUT
    One or more text messages: first possibly commentary, finally a summary of the last
    3 commits and the line count of README.md. Tool calls themselves are not printed;
    only text blocks are.

REPO MODULES USED
    playbook.common: get_client(), model().

GOTCHAS / TRY NEXT
    * `tool_runner` lives under `client.beta`: the helper is still in the SDK's beta
      namespace, so its surface may change between SDK versions.
    * Iterating the runner yields one assistant Message per model turn (not per tool).
    * count_lines rejects absolute paths and ".." because the model chooses the path.
      The check is deliberately crude; a hardened version would resolve the path and
      compare it with the project root.
    * Next: example 06 sends images and PDFs.
"""
import subprocess

from anthropic import beta_tool

from playbook.common import get_client, model


# @beta_tool inspects this function: name -> tool name, type hints -> input schema,
# docstring -> description. Do not remove the "Args:" section; the model sees it.
@beta_tool
def git_log(max_count: int = 5) -> str:
    """Show the most recent commits of the current repository.

    Args:
        max_count: How many commits to return (1-20).
    """
    # Clamp the model-supplied number: never trust tool input. int() guards against
    # a numeric string; min/max keep the output small enough for the context window.
    max_count = max(1, min(int(max_count), 20))
    # The command is a fixed argument list (no shell=True) so the model cannot inject
    # extra shell commands; only the clamped integer varies.
    out = subprocess.run(["git", "log", f"-{max_count}", "--pretty=%h %s"], capture_output=True, text=True)
    # On failure git writes to stderr; returning it lets the model see what went wrong.
    return out.stdout or out.stderr


@beta_tool
def count_lines(path: str) -> str:
    """Count lines in a text file inside the current directory.

    Args:
        path: Relative file path.
    """
    if path.startswith(("/", "\\")) or ".." in path:  # tool inputs are untrusted
        return "error: only relative paths inside the project are allowed"
    try:
        with open(path, encoding="utf-8") as fh:
            return str(sum(1 for _ in fh))
    except OSError as exc:
        # Return the error as text so the model can recover (e.g. try another path).
        return f"error: {exc}"


if __name__ == "__main__":
    # beta.messages.tool_runner returns an iterable "runner". Each iteration performs one
    # model call; if the reply asks for tools the runner executes them and sends the
    # results automatically on the next iteration.
    runner = get_client().beta.messages.tool_runner(
        # tools: the decorated functions themselves (the SDK reads their generated schemas).
        # max_tokens: output cap for EACH model call in the loop.
        model=model(), max_tokens=2000, tools=[git_log, count_lines],
        messages=[{"role": "user", "content": "Summarise the last 3 commits and how long README.md is."}],
    )
    for message in runner:
        # message.content is a list of blocks. "text" blocks are prose for the user;
        # "tool_use" blocks (skipped here) are the model's requests to run a tool.
        for block in message.content:
            if block.type == "text":
                print(block.text)
