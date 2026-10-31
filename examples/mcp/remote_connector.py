#!/usr/bin/env python3
"""MCP option 3 - the API's MCP connector: Claude connects to a REMOTE MCP server itself.

WHAT THIS FILE IS
  The third way to use MCP (the others: Claude Code reading .mcp.json, and
  client_with_claude.py which runs a local client). Here YOUR code does not speak MCP at
  all: you tell the Messages API where a remote MCP server lives and Anthropic's
  infrastructure connects to it, lists its tools, lets Claude call them and returns the
  results inside the response. No local session and no tool loop.

WHEN TO USE IT
  Only when the server is reachable from the public internet over HTTPS (HTTP/SSE-style
  transports). It cannot reach a stdio server on your laptop, so db_server.py and
  devtools_server.py are NOT usable with it.

BOTH HALVES ARE REQUIRED
  * `mcp_servers` declares the server (type url, the url, and a name).
  * a `mcp_toolset` entry in `tools` enables that server's tools, referring to it by the
    same name. Declaring the server without the toolset exposes nothing to the model.
  The `betas` flag opts in to the beta MCP connector; the dated flag may be superseded, so
  check current API docs if the call is rejected.

HOW TO RUN (from the repo root; needs ANTHROPIC_API_KEY and a real remote server URL)
  MCP_SERVER_URL=https://mcp.example.com/sse python examples/mcp/remote_connector.py
  (PowerShell: $env:MCP_SERVER_URL="https://..."; python examples/mcp/remote_connector.py)
  example.com above is a placeholder; without MCP_SERVER_URL the script exits with a message.

OUTPUT
  Text blocks are printed as-is; "mcp_tool_use" blocks (tool calls Anthropic made on your
  behalf) are printed as "[mcp call] name input" so you can see what happened.
"""
from __future__ import annotations

import os

from playbook.common import get_client, model


def main() -> None:
    url = os.environ.get("MCP_SERVER_URL")
    if not url:  # fail early with a clear message instead of an opaque API error
        raise SystemExit("Set MCP_SERVER_URL to a remote MCP server (HTTPS).")
    response = get_client().beta.messages.create(
        model=model(),  # resolved centrally; never hardcode model ids in examples
        max_tokens=2000,
        betas=["mcp-client-2025-11-20"],
        mcp_servers=[{"type": "url", "url": url, "name": "remote-tools"}],
        tools=[{"type": "mcp_toolset", "mcp_server_name": "remote-tools"}],
        messages=[{"role": "user", "content": "List what tools you can use, then use one."}],
    )
    for block in response.content:
        if block.type == "text":
            print(block.text)
        elif block.type == "mcp_tool_use":
            print(f"[mcp call] {block.name} {block.input}")


if __name__ == "__main__":
    main()
