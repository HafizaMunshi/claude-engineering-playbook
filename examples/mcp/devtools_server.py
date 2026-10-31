#!/usr/bin/env python3
"""MCP server #2 - everyday dev utilities: log triage and semver reasoning.

WHAT THIS FILE IS
  A second, deliberately simple MCP server (see db_server.py for the database one and for
  the full explanation of MCP, tools vs resources vs prompts, and the initialize /
  list_tools / call_tool handshake). Here there is no database or network: each tool is
  plain deterministic Python, showing an MCP tool can be pure logic.

WHY THE LOGIC IS SPLIT FROM THE TOOLS
  summarize_log_text() and bump_version() are ordinary functions with no MCP dependency so
  tests/test_assets_and_mcp.py can import and unit-test them directly. The @mcp.tool()
  wrappers only adapt them to the protocol (string in, string out, errors as text).

TRANSPORT
  Runs over stdio: a client launches this file as a child process and exchanges JSON-RPC on
  stdin/stdout. Never print() to stdout in this file - it would corrupt the protocol
  stream. Use stderr for diagnostics.

SDK NOTE
  Uses the v2 MCP SDK class MCPServer (called FastMCP in v1).

HOW TO RUN (from the repo root)
  python examples/mcp/devtools_server.py
  It then waits silently for protocol messages; normally Claude Code starts it via .mcp.json.
"""
from __future__ import annotations

import json
import re
from collections import Counter

from mcp.server.mcpserver import MCPServer

mcp = MCPServer("dev-tools", instructions="Small deterministic helpers for logs and versions.")

# Expected log shape: "<timestamp-without-spaces> <LEVEL> <message>". Lines that do not match
# (stack-trace continuations, blank lines) are silently skipped by summarize_log_text.
_LOG_LINE = re.compile(r"^(?P<ts>\S+)\s+(?P<level>DEBUG|INFO|WARN|WARNING|ERROR|FATAL)\s+(?P<msg>.*)$")


def summarize_log_text(text: str, top: int = 5) -> dict:
    """Count levels and rank the most frequent error messages (digits normalised)."""
    levels: Counter[str] = Counter()
    errors: Counter[str] = Counter()  # keyed by message with digits replaced by "N"
    for line in text.splitlines():
        m = _LOG_LINE.match(line.strip())
        if not m:
            continue
        levels[m["level"]] += 1
        if m["level"] in ("ERROR", "FATAL"):
            # Replacing digits groups "timeout after 30 s" and "timeout after 45 s" together,
            # so the ranking shows distinct problems instead of distinct numbers.
            errors[re.sub(r"\d+", "N", m["msg"])] += 1
    return {"levels": dict(levels), "top_errors": errors.most_common(top)}


def bump_version(version: str, part: str) -> str:
    """Return the next semantic version; accepts a leading "v", returns plain x.y.z.

    Raises ValueError for an unknown ``part``. A malformed version (not three integers) also
    raises ValueError from the unpacking/int() below. Resetting lower parts to 0 is the
    semver rule: a minor bump zeroes patch, a major bump zeroes minor and patch.
    """
    major, minor, patch = (int(x) for x in version.lstrip("v").split("."))
    if part == "major":
        return f"{major + 1}.0.0"
    if part == "minor":
        return f"{major}.{minor + 1}.0"
    if part == "patch":
        return f"{major}.{minor}.{patch + 1}"
    raise ValueError("part must be major, minor or patch")


@mcp.tool()
def summarize_log(text: str, top: int = 5) -> str:
    """Summarise a pasted log: counts per level and the most frequent error messages."""
    # MCP tool results are text, so the dict is serialised to JSON.
    return json.dumps(summarize_log_text(text, top))


@mcp.tool()
def next_version(current: str, change: str) -> str:
    """Compute the next semantic version. `change` is one of: major, minor, patch."""
    try:
        return bump_version(current, change)
    except ValueError as exc:
        # Return (not raise) the error so the model sees the reason and can fix its input.
        return f"ERROR: {exc}"


if __name__ == "__main__":
    mcp.run()  # serve over stdio until the client disconnects
