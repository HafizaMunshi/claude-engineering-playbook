#!/usr/bin/env python3
"""PreToolUse hook (matcher: Edit|Write) - keep secrets out of files Claude touches.

WHAT: runs before Claude writes or edits a file.  Claude Code passes a JSON event on
stdin, e.g. ``{"tool_name": "Write", "tool_input": {"file_path": "a.py", "content": "..."}}``.
The script exits 2 (block; stderr is shown to Claude) if either
  * the target file is a well-known credentials file (``.env``, private keys, ...), or
  * the text about to be written looks like a hardcoded secret.
It exits 0 (allow) otherwise.

WHY: a leaked key in a commit is expensive to clean up.  A hook enforces the rule
deterministically, whereas a CLAUDE.md instruction relies on the model remembering it.
Demonstrates the Claude Code hooks feature (see also ``block_dangerous_bash.py``).

HOW IT FITS: wired under ``PreToolUse`` in ``.claude/settings.json``; contract-tested in
``tests/test_hooks.py`` (the tests build fake key-shaped strings at runtime so no real
looking secret is stored in the repo).

Limitations (a safety net, not a guarantee):
  * Only three secret shapes are recognised: an Anthropic-style API key (prefix
    "sk-ant-" then 10+ key characters), an AWS access key id ("AKIA" then 16 upper-case
    letters/digits) and a PEM private-key header.
  * Only the ``content`` (Write) or ``new_string`` (Edit) field is scanned; other tools
    that carry text (e.g. multi-edit batches) and file NAMES like ``.env.local`` are not
    covered.
  * It fails open on malformed JSON so a harness glitch cannot freeze the session.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import PurePath

# Exact file names that conventionally hold credentials:
#   .env (environment secrets), .npmrc / .pypirc (package-registry tokens),
#   id_rsa / id_ed25519 (SSH private keys), credentials (e.g. cloud CLI credential file).
PROTECTED_NAMES = {".env", ".npmrc", ".pypirc", "id_rsa", "id_ed25519", "credentials"}
# Content signatures of secrets.  Each is compiled once at import time.
SECRET_PATTERNS = [
    # Anthropic API key: literal prefix, then 10 or more letters/digits/underscore/hyphen.
    #   [A-Za-z0-9_-]{10,}  character class with a minimum length of 10
    re.compile(r"sk-ant-[A-Za-z0-9_-]{10,}"),
    # AWS access key id: literal "AKIA" + exactly 16 upper-case letters or digits.
    re.compile(r"AKIA[0-9A-Z]{16}"),
    # PEM private key header.  "(RSA |EC |OPENSSH )?" makes the algorithm word optional
    # so the generic "BEGIN PRIVATE KEY" form matches as well.
    re.compile(r"-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----"),
]


def check(path: str, content: str) -> str | None:
    """Return a reason string if the write should be blocked, else None.

    Args:
        path: the ``file_path`` Claude wants to write (only its final component is used).
        content: the text about to be written.
    """
    # PurePath works on strings without touching the disk (the file may not exist yet)
    # and handles both / and \ separators according to the current OS.
    name = PurePath(path).name
    if name in PROTECTED_NAMES or name.endswith((".pem", ".key")):
        return f"{name} is a protected credentials file"
    for pattern in SECRET_PATTERNS:
        if pattern.search(content):
            return "content looks like a hardcoded secret"
    return None


def main() -> int:
    """Read the hook event from stdin; return 0 (allow) or 2 (block)."""
    try:
        event = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0  # fail open: never let a malformed event break the session
    tool_input = event.get("tool_input", {})
    # The Write tool puts the full text in ``content``; the Edit tool puts the
    # replacement text in ``new_string``.  ``or ""`` covers a missing or null value.
    content = tool_input.get("content") or tool_input.get("new_string") or ""
    reason = check(tool_input.get("file_path", ""), content)
    if reason:
        # Exit code 2 + stderr = "block, and tell Claude why" in the hook contract.
        print(f"Blocked by project hook: {reason}. Use environment variables instead.", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
