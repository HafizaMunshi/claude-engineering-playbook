#!/usr/bin/env python3
"""MCP client #1 - talk to a server directly (no LLM): list tools/resources/prompts, call a tool.

WHAT THIS FILE IS
  The minimal MCP CLIENT. It launches db_server.py as a child process, performs the MCP
  handshake and prints what the server offers. Reading it shows what Claude Code does for
  you behind the scenes after reading .mcp.json - without any model involved.

THE CLIENT SIDE OF THE PROTOCOL
  * stdio_client starts the server process and gives us (read, write) streams wired to its
    stdout/stdin (the "stdio transport"; that is why the server must keep stdout clean).
  * ClientSession speaks the protocol over those streams.
  * initialize()      - mandatory handshake; nothing else works before it.
  * list_tools() / list_resources() / list_prompts() - discovery of the three primitives.
  * call_tool(name, args) - execute a tool. Results come back as a list of content blocks;
    for our text tools the answer is content[0].text.

HOW TO RUN (from the repo root - the server path below is relative)
  python examples/mcp/client_demo.py
  No API key needed. The server builds examples/mcp/sample.sqlite if it is missing.
  Expected output: the tool/resource/prompt names and the planted duplicate (customer 2).

RELATED
  client_with_claude.py does the same connection but hands the tools to Claude.
  Uses the v2 MCP SDK (server side class MCPServer; FastMCP in v1).
"""
from __future__ import annotations

import asyncio
import sys

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


async def explore(db_path: str = "examples/mcp/sample.sqlite") -> dict:
    # sys.executable = the same interpreter (and venv) that runs this script, so the server
    # sees the same installed packages. "python" on PATH could be a different one.
    params = StdioServerParameters(command=sys.executable, args=["examples/mcp/db_server.py", "--db", db_path])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()  # handshake; must come first
            tools = await session.list_tools()
            resources = await session.list_resources()
            prompts = await session.list_prompts()
            # The tool runs server-side; our SQL goes through the server's read-only guard.
            result = await session.call_tool(
                "query", {"sql": "SELECT customer_id, COUNT(*) n FROM subscriptions "
                                 "WHERE status='active' GROUP BY customer_id HAVING n > 1"})
            # Flatten the SDK objects to plain strings so they print readably.
            return {
                "tools": [t.name for t in tools.tools],
                "resources": [str(r.uri) for r in resources.resources],
                "prompts": [p.name for p in prompts.prompts],
                "duplicate_active": result.content[0].text,
            }


if __name__ == "__main__":
    for key, value in asyncio.run(explore()).items():
        print(f"{key}: {value}")
