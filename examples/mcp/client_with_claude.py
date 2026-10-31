#!/usr/bin/env python3
"""MCP client #2 - hand an MCP server's tools to Claude via the SDK's MCP helpers.

WHAT THIS FILE IS
  "MCP option 2": a local MCP client that gives a Claude model access to an MCP server's
  tools. Compare client_demo.py (no model, you call tools yourself) and remote_connector.py
  (Anthropic's servers connect to a remote MCP server for you).

HOW IT WORKS
  1. Start db_server.py over stdio and run the MCP handshake (initialize), then list_tools.
  2. async_mcp_tool wraps each MCP tool as an Anthropic API tool: it translates the MCP
     tool schema into an API tool definition AND remembers the session, so when Claude asks
     to use the tool the call is forwarded to session.call_tool and the result returned.
  3. client.beta.messages.tool_runner owns the agentic loop (call model -> run requested
     tools -> send results -> repeat until the model stops). tools.py shows the same loop
     written by hand.

HOW TO RUN (from the repo root)
  export ANTHROPIC_API_KEY=...   (PowerShell: $env:ANTHROPIC_API_KEY="...")
  python examples/mcp/client_with_claude.py
  Makes live, billable API calls. Uses the default DB path, creating sample.sqlite if absent.

GOTCHAS
  * Run from the repo root: the server script path is relative.
  * The model id comes from playbook.common.model(); do not hardcode it here.
  * Iterating the runner yields one assistant message per loop turn; we print only text
    blocks (tool_use blocks are handled inside the runner).
"""
from __future__ import annotations

import asyncio
import sys

import anthropic
from anthropic.lib.tools.mcp import async_mcp_tool
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from playbook.common import model

QUESTION = "Does any customer have more than one active subscription? Name them and the plans."


async def main() -> None:
    client = anthropic.AsyncAnthropic()  # async client because the MCP session is async
    # sys.executable keeps the child on the same interpreter/venv as this script.
    params = StdioServerParameters(command=sys.executable, args=["examples/mcp/db_server.py"])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = (await session.list_tools()).tools  # MCP tool definitions (name, schema)
            runner = client.beta.messages.tool_runner(
                model=model(), max_tokens=4096,
                tools=[async_mcp_tool(t, session) for t in tools],
                messages=[{"role": "user", "content": QUESTION}],
            )
            # Each iteration is one assistant turn; tool execution happens inside the runner.
            async for message in runner:
                for block in message.content:
                    if block.type == "text":
                        print(block.text)


if __name__ == "__main__":
    asyncio.run(main())
