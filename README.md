# Claude Engineering Playbook

Hands-on proof of work for three Anthropic courses - **Claude 101**, **Claude Code 101** and
**Building with the Claude API** - applied to everyday senior-software-engineer tasks:
code review, incident RCA, database investigation, testing, ADRs, release notes, log triage.

Everything is generic and synthetic. No employer code, data, credentials or product names.

> **New here?** Read [GUIDE.md](GUIDE.md) - a tour of every skill, subagent, command, hook, MCP server
> and example, with how to run and extend each.

## Quick start
```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pytest                                    # 58 offline tests, no API key needed
python scripts/validate_claude_assets.py  # lints skills, agents, commands, hooks, MCP config
export ANTHROPIC_API_KEY=...              # only for the live examples below
python examples/api/01_first_message.py
```

## What is where

### Claude Code 101 - `.claude/`
| Feature | Files | Senior-engineer use case |
|---------|-------|--------------------------|
| **Skills** (6) | `.claude/skills/{pr-review, incident-rca, readonly-db-investigation, write-unit-tests, adr-writer, release-notes}` | Review, postmortems, safe data debugging, tests, decisions, changelogs. DB skill bundles a guarded script; RCA skill bundles a template. |
| **Subagents** (5) | `.claude/agents/{code-reviewer, test-writer, security-auditor, debugger, docs-writer}.md` | Least-privilege tools, per-agent model choice, separate context windows. |
| **Slash commands** (4) | `.claude/commands/{pr-summary, triage-bug, standup, explain-diff}.md` | `$ARGUMENTS`, `!` shell pre-run, `@file` attachments, `allowed-tools`. |
| **Hooks** (3) | `.claude/hooks/*.py` | Block destructive shell commands, block secrets in edits, audit log. Contract-tested in `tests/test_hooks.py`. |
| **Permissions** | `.claude/settings.json` | Allow read-only commands, deny `.env` reads and force pushes. |
| **Project memory** | `CLAUDE.md`, `templates/CLAUDE.{backend-service,data-pipeline,frontend-app,infra-as-code}.md` | Ready-to-copy project instructions for four common project types. |
| **MCP config** | `.mcp.json` | Project-scoped servers. |

### Claude 101 - prompting and Projects
- `examples/claude_101/prompt_patterns.py` - role/audience, XML structure, few-shot, reason-then-answer, admit-unknowns.
- `claude_projects/*.md` - custom instructions for three Claude Projects (code review, incident commander, docs writer).

### Building with the Claude API - `examples/api/`
| # | Concept | # | Concept |
|---|---------|---|---------|
| 01 | Messages, system prompt, multi-turn | 09 | Message Batches |
| 02 | Streaming | 10 | Citations |
| 03 | Structured outputs (Pydantic) | 11 | RAG without a vector DB |
| 04 | Tool use - manual agent loop | 12 | Workflows: chain, route, parallelize, evaluator-optimizer |
| 05 | Tool runner (`@beta_tool`) | 13 | Prompt evaluations |
| 06 | Images and PDFs | 14 | Server tools: code execution, web search |
| 07 | Prompt caching | 15 | Typed errors, retries, token counting |
| 08 | Adaptive thinking + effort | | |

### MCP - `examples/mcp/`
| File | Shows |
|------|-------|
| `db_server.py` | Server with a tool, a resource and a prompt over a read-only DB |
| `devtools_server.py` | Pure-logic server: log triage, semver |
| `client_demo.py` | Raw MCP client over stdio (no LLM) |
| `client_with_claude.py` | MCP tools handed to Claude via the SDK helpers |
| `remote_connector.py` | The API's MCP connector for remote servers |

## Design choices worth noting
- **Testable by construction:** loop, workflow and eval logic live in `src/playbook/` and take a `client`, so tests inject a scripted fake instead of calling the network.
- **Safety in depth for data access:** SQL allow-list + read-only connection + row cap, and fix-SQL is only ever produced as text.
- **Tool inputs are untrusted:** the calculator uses an AST walker, never `eval`.
- **Current API conventions:** adaptive thinking and `effort` instead of budgets, structured outputs instead of prefill, no sampling parameters, `tool_choice: auto` with strict schemas.

## Verification status
- Offline: `pytest` (58 tests, including real stdio round-trips to the MCP server) and the asset linter pass.
- Live API examples compile and import cleanly but need your `ANTHROPIC_API_KEY` to run.

See `docs/concept-map.md` for the full course-topic-to-file mapping.
