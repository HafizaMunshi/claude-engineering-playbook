# CLAUDE.md - claude-engineering-playbook

Project memory for Claude Code. Keep it short; it is loaded every session.

## What this repo is
A practical portfolio of patterns from three Anthropic courses (Claude 101,
Claude Code 101, Building with the Claude API), applied to everyday senior
software engineering work. Everything is generic - no employer or product
specifics, no real credentials, no real data.

## Layout
- `.claude/skills/`    reusable skills (one folder + SKILL.md each)
- `.claude/agents/`    subagents with scoped tools
- `.claude/commands/`  slash commands
- `.claude/hooks/`     hook scripts wired in `.claude/settings.json`
- `.mcp.json`          project-scoped MCP servers
- `src/playbook/`      shared helpers; `examples/` runnable demos; `tests/` offline tests
- `templates/`         CLAUDE.md templates for common project types
- `docs/`              course-to-repo concept map

## Commands
```bash
python -m venv .venv && .venv/Scripts/activate   # or source .venv/bin/activate
pip install -e ".[dev]"
pytest                                           # offline, no API key needed
python scripts/validate_claude_assets.py         # lints skills/agents/commands
python examples/api/01_first_message.py          # live examples need ANTHROPIC_API_KEY
```

## Conventions
- Python 3.10+, type hints, small functions that take a `client` argument so tests can inject a fake.
- Models come from `playbook.common.model()` - never hardcode ids in examples.
- Do not pass `temperature`/`top_p`/`top_k` (rejected by current models); steer with prompts and `effort`.
- No assistant prefill; use structured outputs or instructions to control format.
- Tool inputs are untrusted: validate before executing. SQL tools are read-only by construction.
- Never commit `.env`, keys, or generated `.sqlite` files.

## Definition of done
`pytest` green, `validate_claude_assets.py` clean, README table updated if an example was added.
