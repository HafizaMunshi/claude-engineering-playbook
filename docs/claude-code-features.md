# Claude Code features used in this repo

## CLAUDE.md (project memory)
A markdown file loaded into every session. Keep it short: commands, conventions, guardrails.
Templates for four project types are in `templates/`. Hierarchy: user-level, project root, and
sub-folder files stack, with the most specific winning.

## Skills
A skill is a folder with a `SKILL.md` (YAML frontmatter `name` + `description`, then instructions)
and optional `scripts/` or `templates/`. Claude reads only the descriptions up front and loads the
body when the task matches - this is progressive disclosure, which keeps context small.

## Subagents
Markdown files in `.claude/agents/` with their own tool allow-list and model. They run in a separate
context window and return only a summary, so noisy work (searching, reviewing) does not pollute the
main conversation. Give each the minimum tools it needs.

## Slash commands
Markdown prompts in `.claude/commands/`. They accept `$ARGUMENTS`, can pre-run shell commands with a
leading `!` and attach files with `@path`.

## Hooks
Hooks are deterministic scripts that run on events such as PreToolUse, PostToolUse and SessionStart.
A PreToolUse hook that exits with code 2 blocks the tool call before it runs and sends its stderr back
to Claude. Use hooks for rules that must always hold (block `rm -rf`, protect secrets) instead of
hoping the model remembers an instruction.

## MCP
The Model Context Protocol connects Claude to external tools and data. Servers expose tools, resources
and prompts. Project-scoped servers are declared in `.mcp.json`.

## Permissions
`settings.json` lists allow and deny rules per tool pattern. Deny always wins. Read-only commands are
safe to pre-approve; anything that mutates shared state should prompt.
