#!/usr/bin/env python3
"""Lint the Claude Code assets in this repo (skills, agents, commands, settings, MCP).

Exit code 0 = clean, 1 = problems found. Used by CI and by tests/test_assets.py.

WHAT: a dependency-free checker that reads the configuration files Claude Code uses
(skill/agent/command markdown files with YAML "frontmatter", ``.claude/settings.json``
and ``.mcp.json``) and reports mistakes that would otherwise fail silently, e.g. a
skill whose name does not match its folder (so it never loads) or a hook that points at
a script that no longer exists.

WHY: Claude Code ignores or mis-loads malformed assets without a loud error, so a
cheap automated lint catches them early.  Definition of done in CLAUDE.md requires this
script to be clean.

HOW IT FITS: each ``check_*`` function inspects one asset type and returns a list of
error strings; ``main`` concatenates them, prints them and sets the exit code.  The
default arguments point at this repo's real folders, while tests can pass a temporary
folder instead.

Usage (from the repo root):
    python scripts/validate_claude_assets.py       # prints "OK" or one ERROR line each

Limitations:
  * The frontmatter parser is intentionally tiny: only single-line ``key: value`` pairs
    (no nested YAML, no multi-line values) and it expects Unix ``\\n`` line endings.
    A file saved with Windows CRLF line endings would be reported as "missing YAML
    frontmatter".
  * Hook script existence is checked only for command tokens ending in ``.py``.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

# This file lives in <repo>/scripts/, so two ``.parent`` hops reach the repo root.
# ``resolve()`` makes the path absolute so it works from any working directory.
ROOT = Path(__file__).resolve().parent.parent
CLAUDE = ROOT / ".claude"
# Skill names: lowercase words/digits joined by SINGLE hyphens.
#   ^[a-z0-9]+      first word (letters/digits only)
#   (-[a-z0-9]+)*   zero or more "-word" groups (so no leading, trailing or double hyphen)
#   $               end of string
NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
# The hook event names Claude Code recognises; anything else in settings.json is a typo.
VALID_HOOK_EVENTS = {"PreToolUse", "PostToolUse", "UserPromptSubmit", "Stop", "SubagentStop",
                     "SessionStart", "SessionEnd", "Notification", "PreCompact"}


def parse_frontmatter(text: str) -> dict[str, str]:
    """Minimal YAML-subset parser: `key: value` lines between the first two `---`.

    Example input::

        ---
        name: my-skill
        description: Use when ...
        ---
        (markdown body)

    Regex pieces: ``^---\\n`` the file must START with a ``---`` line; ``(.*?)`` the
    shortest possible block of text (non-greedy, so it stops at the FIRST closing
    marker); ``\\n---\\n`` the closing marker line; ``re.DOTALL`` lets ``.`` match
    newlines so the block can span many lines.

    Returns:
        ``{key: value}`` with whitespace stripped.  Values stay strings.  Only the first
        ``:`` splits a line, so values may themselves contain colons.
    Raises:
        ValueError: if there is no frontmatter block.
    """
    match = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if not match:
        raise ValueError("missing YAML frontmatter")
    fields: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            fields[key.strip()] = value.strip()
    return fields


def check_skills(root: Path = CLAUDE) -> list[str]:
    """Validate every ``skills/<folder>/SKILL.md``.

    Rules enforced:
      * frontmatter exists;
      * ``name`` equals the folder name (Claude Code identifies a skill by it);
      * ``name`` is lowercase-hyphen (``NAME_RE``);
      * ``description`` is at least 40 characters - Claude decides WHETHER to load a
        skill by reading only its description, so a vague one never triggers;
      * the description contains the word "use" or "when", i.e. it says WHEN to apply.
    Returns a list of error strings (empty if all is well).
    """
    errors = []
    for skill_md in sorted((root / "skills").glob("*/SKILL.md")):
        folder = skill_md.parent.name
        try:
            meta = parse_frontmatter(skill_md.read_text(encoding="utf-8"))
        except ValueError as exc:
            errors.append(f"{skill_md}: {exc}")
            continue  # no metadata to check further
        if meta.get("name") != folder:
            errors.append(f"{skill_md}: name {meta.get('name')!r} must equal folder {folder!r}")
        if not NAME_RE.match(meta.get("name", "")):
            errors.append(f"{skill_md}: name must be lowercase-hyphen")
        desc = meta.get("description", "")
        if len(desc) < 40:
            errors.append(f"{skill_md}: description too short to trigger reliably (<40 chars)")
        if not re.search(r"\b(use|when)\b", desc, re.IGNORECASE):
            errors.append(f"{skill_md}: description should say WHEN to use the skill")
    return errors


def check_agents(root: Path = CLAUDE) -> list[str]:
    """Validate every subagent file ``agents/*.md``.

    Rules: frontmatter exists; ``name`` equals the file name without ``.md``; a
    non-empty ``description`` (the main agent reads it to decide when to delegate); and
    a ``tools`` key must be present.  Requiring ``tools`` forces a deliberate choice of
    permissions (least privilege) instead of silently inheriting every tool.
    """
    errors = []
    for agent_md in sorted((root / "agents").glob("*.md")):
        try:
            meta = parse_frontmatter(agent_md.read_text(encoding="utf-8"))
        except ValueError as exc:
            errors.append(f"{agent_md}: {exc}")
            continue
        if meta.get("name") != agent_md.stem:
            errors.append(f"{agent_md}: name must equal filename")
        if not meta.get("description"):
            errors.append(f"{agent_md}: description required")
        if "tools" not in meta:
            errors.append(f"{agent_md}: declare tools explicitly (least privilege)")
    return errors


def check_commands(root: Path = CLAUDE) -> list[str]:
    """Validate every slash-command file ``commands/*.md``: frontmatter + description.

    The description is what appears in the ``/`` command menu.
    """
    errors = []
    for cmd in sorted((root / "commands").glob("*.md")):
        try:
            meta = parse_frontmatter(cmd.read_text(encoding="utf-8"))
        except ValueError as exc:
            errors.append(f"{cmd}: {exc}")
            continue
        if not meta.get("description"):
            errors.append(f"{cmd}: description required")
    return errors


def check_settings(root: Path = CLAUDE) -> list[str]:
    """Validate ``settings.json``: it parses, hook event names are known, scripts exist.

    Structure being walked::

        {"hooks": {"<EventName>": [ {"matcher": "...",
                                     "hooks": [ {"type": "command", "command": "python x.py"} ]} ]}}

    Every whitespace-separated token of each hook command that ends in ``.py`` must be
    an existing file, resolved relative to the repo root (``root.parent``, since
    ``root`` is the ``.claude`` folder).  A missing/invalid settings file is returned
    as a single error rather than raised.
    """
    errors = []
    path = root / "settings.json"
    try:
        settings = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"{path}: {exc}"]
    for event, groups in settings.get("hooks", {}).items():
        if event not in VALID_HOOK_EVENTS:
            errors.append(f"{path}: unknown hook event {event}")
        for group in groups:
            for hook in group.get("hooks", []):
                for token in hook.get("command", "").split():
                    if token.endswith(".py") and not (root.parent / token).exists():
                        errors.append(f"{path}: hook script missing: {token}")
    return errors


def check_mcp(root: Path = ROOT) -> list[str]:
    """Validate ``.mcp.json``: it parses, each server has a ``command``, scripts exist.

    Note ``root`` here is the REPO root (not ``.claude``), because ``.mcp.json`` sits at
    the top level.  Any argument ending in ``.py`` must exist relative to that root.
    """
    errors = []
    path = root / ".mcp.json"
    try:
        servers = json.loads(path.read_text(encoding="utf-8")).get("mcpServers", {})
    except (OSError, json.JSONDecodeError) as exc:
        return [f"{path}: {exc}"]
    for name, cfg in servers.items():
        if "command" not in cfg:
            errors.append(f"{path}: server {name} missing command")
        for arg in cfg.get("args", []):
            if arg.endswith(".py") and not (root / arg).exists():
                errors.append(f"{path}: server {name} script missing: {arg}")
    return errors


def main() -> int:
    """Run every check, print the results and return the process exit code (0/1)."""
    errors = check_skills() + check_agents() + check_commands() + check_settings() + check_mcp()
    for err in errors:
        print(f"ERROR {err}")
    print("OK" if not errors else f"{len(errors)} problem(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    # sys.exit turns main()'s integer into the real process exit status (used by CI).
    sys.exit(main())
