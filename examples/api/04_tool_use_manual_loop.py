#!/usr/bin/env python3
"""Concept: tool use - the manual agentic loop over a read-only database + calculator.

WHAT IT SHOWS
    Claude answers a data question ("total invoiced dollars per country") by calling
    tools: it inspects the database schema, runs a SELECT, and uses a calculator for the
    arithmetic. This file only wires things together; the loop itself is in
    playbook.tools.run_agent_loop and is unit-tested offline with a fake client.

COURSE CONCEPT (Building with the Claude API: tool use)
    The model cannot touch your systems; it can only ASK you to run a function. The
    contract is:
      1. send `tools` (name, description, JSON schema) with the messages;
      2. if the response has stop_reason == "tool_use", it contains `tool_use` content
         blocks (each with an id, a tool name and an input dict);
      3. run EVERY tool_use block and reply with ONE user message holding a
         `tool_result` block per call, each carrying the matching `tool_use_id`;
      4. repeat until the model answers with plain text (stop_reason "end_turn").
    This is the foundation of every agent. Tool inputs come from a model, so treat them
    as untrusted: here the SQL goes through an allow-list guard and a read-only DB
    connection, and the calculator uses an AST walker, never eval().

HOW TO RUN (from the repo root)
    export ANTHROPIC_API_KEY=...        # Windows PowerShell: $env:ANTHROPIC_API_KEY="..."
    python examples/api/04_tool_use_manual_loop.py
    It writes a throwaway SQLite file to build/demo.sqlite (recreated each run).

EXPECTED OUTPUT
    A trace line per tool call (printed by on_event, e.g. `turn 1: describe_schema(...)`),
    then `FINAL:` followed by a per-country dollar total. The sample data are four
    synthetic customers and four invoices stored in cents, so the model should convert
    cents to dollars (that is what the calculator is for).

REPO MODULES USED
    playbook.sampledb (builds the synthetic DB), playbook.sqlguard (read-only connection
    and SELECT-only validation), playbook.tools (tool schemas, handlers, run_agent_loop),
    playbook.common (get_client).

GOTCHAS / TRY NEXT
    * The loop is capped by max_turns so a confused model cannot run forever.
    * Tool errors are sent back to the model as `tool_result` with is_error=true so it
      can fix its query, rather than crashing the program.
    * Compare with example 05, where the SDK runs this loop for you.
"""
from playbook import sampledb, sqlguard
from playbook.common import get_client
from playbook.tools import make_toolset, run_agent_loop

if __name__ == "__main__":
    # Build a small synthetic SQLite database (customers, subscriptions, invoices).
    db = sampledb.build("build/demo.sqlite")
    # Re-open it READ-ONLY (SQLite mode=ro): even if the SQL guard missed something,
    # the connection itself cannot write. Defence in depth.
    conn = sqlguard.open_readonly(str(db))
    # tools = JSON schemas shown to the model; handlers = the Python functions that
    # actually run when the model calls a tool (keyed by tool name).
    tools, handlers = make_toolset(conn)
    answer = run_agent_loop(
        get_client(),
        "What is the total invoiced amount in dollars per country? Use the database and the calculator.",
        tools, handlers,
        # The system prompt nudges good habits: look at the schema first and never
        # invent numbers (a tool exists for exact data and maths).
        system="You answer data questions. Inspect the schema before querying. Never guess numbers.",
        # on_event receives one human-readable line per tool call; print shows the trace.
        on_event=print,
    )
    print("\nFINAL:", answer)
