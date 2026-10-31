#!/usr/bin/env python3
"""PreToolUse hook (matcher: Bash) - veto destructive shell commands.

Claude Code sends a JSON event on stdin. Exiting with code 2 blocks the tool
call and feeds stderr back to Claude so it can pick a safer approach.

WHAT: before Claude runs any Bash command, Claude Code starts this script and writes an
event like ``{"tool_name": "Bash", "tool_input": {"command": "rm -rf /"}}`` to its
standard input.  The script answers through its exit code:
  * 0 - allow the command to proceed;
  * 2 - BLOCK it; whatever was printed to stderr is shown to Claude as the reason.

WHY: this demonstrates Claude Code "hooks" - deterministic code that runs at fixed
points in the agent's lifecycle.  Unlike an instruction in CLAUDE.md (which the model
may ignore), a hook is enforced by the harness, so it is the right tool for hard rules.

HOW IT FITS: registered under ``PreToolUse`` in ``.claude/settings.json`` (the
validator ``scripts/validate_claude_assets.py`` checks that path exists).  Contract
tests are in ``tests/test_hooks.py``.  Sibling hooks: ``protect_secrets.py`` (blocks
secrets in edits) and ``log_tool_use.py`` (audit log).

Limitations: this is a deny-list of regular expressions, so it is a safety net, not a
sandbox.  It can be bypassed by obfuscation (``rm -r -f``, ``rm --recursive --force``,
variables, scripts that delete internally).  Real isolation needs permissions rules or
a sandboxed environment as well.
"""
from __future__ import annotations

import json
import re
import sys

# (regex, human-readable reason) pairs.  The reason is shown to Claude when blocked.
# All patterns are searched case-insensitively (see ``check``).
# Regex notation used below: \b = word boundary, \s = whitespace, [^|] = any char
# except a pipe, .* = anything, (a|b) = alternatives.
BLOCKED = [
    # rm with BOTH a recursive (r) and force (f) flag in one option group, in either
    # order: "rm -rf x", "rm -fr x", "rm -Rf x" (IGNORECASE makes r/R match).
    #   \brm\s+            the word rm followed by whitespace
    #   -[a-zA-Z]*r[a-zA-Z]*f   dash, other letters, an r, other letters, then f  (-rf, -rvf)
    #   -[a-zA-Z]*f[a-zA-Z]*r   same with f before r                             (-fr)
    #   \b                 end of the flag cluster
    # Plain "rm file.txt" and "rm -r dir" (no force) are deliberately allowed.
    (r"\brm\s+(-[a-zA-Z]*r[a-zA-Z]*f|-[a-zA-Z]*f[a-zA-Z]*r)\b", "recursive force delete"),
    # git push followed (anywhere later on the line) by --force or -f.
    #   --force\b   also matches --force-with-lease, which is therefore blocked too
    #   \s-f\b      a standalone -f flag (the \s avoids matching dashes inside branch names)
    # Rewriting shared history can destroy other people's commits.
    (r"\bgit\s+push\b.*(--force\b|\s-f\b)", "force push"),
    # reset --hard throws away uncommitted work irreversibly.
    (r"\bgit\s+reset\s+--hard\b", "hard reset discards work"),
    # Destructive SQL typed into a shell client such as psql or sqlite3.
    (r"\bdrop\s+(table|database)\b", "destructive SQL"),
    # "curl URL | sh" runs unreviewed remote code.
    #   (curl|wget)       a downloader
    #   [^|]*             anything up to the first pipe
    #   \|\s*             the pipe
    #   (sudo\s+)?        optional sudo
    #   (ba|z)?sh         sh, bash or zsh
    (r"\b(curl|wget)\b[^|]*\|\s*(sudo\s+)?(ba|z)?sh\b", "pipe from network to shell"),
    # chmod -R 777 makes a whole tree writable by everybody.
    (r"\bchmod\s+-R\s+777\b", "world-writable permissions"),
]


def check(command: str) -> str | None:
    """Return a reason string if the command should be blocked, else None.

    The first matching pattern wins.  ``re.search`` finds a match anywhere in the
    command, so the dangerous part can sit in the middle of a longer pipeline.
    """
    for pattern, reason in BLOCKED:
        if re.search(pattern, command, re.IGNORECASE):
            return reason
    return None


def main() -> int:
    """Read the hook event from stdin and return the exit code (0 allow, 2 block)."""
    try:
        event = json.load(sys.stdin)
    except json.JSONDecodeError:
        # Fail OPEN: a malformed event means a harness problem, and crashing the hook
        # would make every Bash call fail and stall the whole session.
        return 0  # never break the session on malformed input
    # The settings matcher already limits this hook to Bash; this is a second check
    # in case the hook is wired up more broadly by mistake.
    if event.get("tool_name") != "Bash":
        return 0
    reason = check(event.get("tool_input", {}).get("command", ""))
    if reason:
        # stderr (not stdout) is what Claude Code feeds back to the model on exit code 2.
        print(f"Blocked by project hook: {reason}. Propose a safer alternative or ask the user.", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
