"""Lint the Claude Code assets and exercise the MCP servers over real stdio.

WHAT THIS FILE COVERS
  1. Asset validation: scripts/validate_claude_assets.py checks skills, agents, commands,
     settings and .mcp.json; here we assert the repo's own assets pass, and that the
     validator really catches a bad skill (so "no errors" is meaningful).
  2. The read-only skill script (safe_query.py) refuses writes.
  3. The pure-logic helpers of the dev-tools MCP server, imported and called directly.
  4. A true end-to-end MCP test: spawn db_server.py as a subprocess, connect with the MCP
     client over stdio (initialize -> list_tools -> call_tool), as Claude Code would.

NOTE ON load()
  The scripts are not importable packages, so load() imports them by file path with
  importlib. They are not added to sys.modules, which is fine for these simple modules.

Run: .venv\\Scripts\\python.exe -m pytest tests/test_assets_and_mcp.py -q
"""
import asyncio
import importlib.util
import json
import sys
from pathlib import Path

import pytest
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

ROOT = Path(__file__).resolve().parent.parent


def load(path: str, name: str):
    # Import a Python file by repo-relative path under an arbitrary module name.
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


validator = load("scripts/validate_claude_assets.py", "validator")
safe_query = load(".claude/skills/readonly-db-investigation/scripts/safe_query.py", "safe_query")
devtools = load("examples/mcp/devtools_server.py", "devtools")


def test_repo_assets_are_valid():
    """All skills, agents, commands, settings and MCP config in the repo pass the linter.

    Acts as the CI gate (same checks as `python scripts/validate_claude_assets.py`): a typo
    in front-matter or a malformed .mcp.json fails here before Claude Code silently ignores it.
    """
    errors = (validator.check_skills() + validator.check_agents() + validator.check_commands()
              + validator.check_settings() + validator.check_mcp())
    assert errors == []


def test_validator_catches_bad_skill(tmp_path):
    """A skill with a bad name (uppercase/underscore) and a too-short description is flagged.

    Negative control for the test above: proves the validator can fail, so a green
    test_repo_assets_are_valid is trustworthy. Expects at least 3 distinct errors.
    """
    bad = tmp_path / "skills" / "Bad_Name"
    bad.mkdir(parents=True)
    (bad / "SKILL.md").write_text("---\nname: Bad_Name\ndescription: short\n---\nbody", encoding="utf-8")
    assert len(validator.check_skills(tmp_path)) >= 3


def test_skill_script_blocks_writes(sample_db):
    """The skill's standalone query script rejects DELETE but runs a SELECT (4 customers).

    The skill ships its own copy of the guard (skills must be self-contained), so it needs
    its own test; a regression would let a skill-driven query modify data.
    """
    with pytest.raises(ValueError):
        safe_query.validate("DELETE FROM customers")
    rows = safe_query.run(safe_query.connect_readonly(str(sample_db)), "SELECT COUNT(*) AS n FROM customers")
    assert rows == [{"n": 4}]


def test_log_summary_and_semver():
    """Dev-tools helpers: level counts, digit-normalised error grouping, semver bumping.

    The two timeout errors differ only in a number and must group as "timeout after N s"
    (count 2). Also checks the "v" prefix is stripped, minor bump resets patch (1.4.9 ->
    1.5.0) and an invalid part raises ValueError.
    """
    log = ("2026-01-01T10:00:00 INFO boot ok\n2026-01-01T10:00:01 ERROR timeout after 30 s\n"
           "2026-01-01T10:00:02 ERROR timeout after 45 s\n")
    summary = devtools.summarize_log_text(log)
    assert summary["levels"] == {"INFO": 1, "ERROR": 2}
    assert summary["top_errors"][0] == ("timeout after N s", 2)
    assert devtools.bump_version("v1.4.9", "minor") == "1.5.0"
    with pytest.raises(ValueError):
        devtools.bump_version("1.0.0", "huge")


async def _call_db_server(db: Path):
    # Mirrors what a real MCP client does: spawn the server, handshake, discover, call.
    # Absolute script path (ROOT) so the test does not depend on the current directory.
    params = StdioServerParameters(command=sys.executable,
                                   args=[str(ROOT / "examples/mcp/db_server.py"), "--db", str(db)])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = sorted(t.name for t in (await session.list_tools()).tools)
            # One valid query and one malicious one, to check both paths over the wire.
            ok = await session.call_tool("query", {"sql": "SELECT COUNT(*) AS n FROM customers"})
            bad = await session.call_tool("query", {"sql": "DROP TABLE customers"})
            return tools, ok.content[0].text, bad.content[0].text


def test_db_mcp_server_over_stdio(sample_db):
    """The DB server works end to end over stdio: right tools, valid query, blocked write.

    Protects the real integration that unit tests cannot: the server starts, stdout carries
    only protocol messages (a stray print would break the handshake and hang/fail here),
    tool discovery lists exactly list_tables and query, a SELECT returns JSON, and
    DROP TABLE comes back as text beginning "ERROR" instead of an exception or success.
    """
    tools, ok, bad = asyncio.run(_call_db_server(sample_db))
    assert tools == ["list_tables", "query"]
    assert json.loads(ok) == [{"n": 4}]
    assert bad.startswith("ERROR")
