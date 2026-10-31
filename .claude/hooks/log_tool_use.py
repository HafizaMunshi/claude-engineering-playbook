#!/usr/bin/env python3
"""PostToolUse hook - append a one-line audit record per tool call (never blocks).

WHAT: after every tool call Claude Code runs this script and sends the event as JSON on
stdin.  The script appends ONE line to ``tool-use.log`` (in this same folder):
``<UTC timestamp> <tool name> <first 120 chars of the tool input>``.

WHY: gives you a simple trail of what the agent did, useful for reviewing a session or
debugging.  Demonstrates a PostToolUse hook, which runs AFTER the tool and therefore
cannot veto it (compare the PreToolUse hooks ``block_dangerous_bash.py`` and
``protect_secrets.py``).  This one always returns 0, so it can never disturb the session.

HOW IT FITS: registered under ``PostToolUse`` in ``.claude/settings.json``.  The log
file matches the ``.claude/hooks/*.log`` rule in ``.gitignore`` so it is never committed.

Limitations:
  * Tool inputs are logged verbatim (truncated to 120 characters), so a secret that
    appears at the start of an input would be written to the log; keep the log local.
  * The file grows forever (no rotation) and concurrent sessions may interleave lines.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# ``with_name`` swaps the final component of this script's path, giving
# ``<hooks folder>/tool-use.log`` regardless of the directory Claude Code runs from.
LOG = Path(__file__).with_name("tool-use.log")


def main() -> int:
    """Append one audit line for the event on stdin; always return 0."""
    try:
        event = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0  # ignore unparseable events silently - an audit hook must never fail loudly
    # Flatten to one line: truncate to 120 characters and replace newlines so every
    # record occupies exactly one line of the log.
    summary = str(event.get("tool_input", {}))[:120].replace("\n", " ")
    # Timezone-aware UTC timestamp avoids ambiguity between machines and daylight-saving.
    line = f"{datetime.now(timezone.utc).isoformat()} {event.get('tool_name', '?')} {summary}\n"
    # Mode "a" appends; the file is created on first use.
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
