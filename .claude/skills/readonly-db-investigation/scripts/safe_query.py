#!/usr/bin/env python3
"""Guarded, read-only SQLite query helper used by the readonly-db-investigation skill.

Usage:
    safe_query.py <db-file> "SELECT ..."
    safe_query.py <db-file> --schema

Standalone on purpose (stdlib only) so the skill folder is portable.

WHAT: a command-line tool Claude runs (via the Bash tool) to look at data in a SQLite
file without any possibility of changing it.  ``--schema`` prints the CREATE TABLE
statements; otherwise the second argument is run as a query and printed as a simple
``a | b | c`` table followed by ``(N rows)``.

WHY: this is the script the skill bundles, demonstrating that a skill can ship
executable helpers next to its SKILL.md instructions.  Safety comes in layers:
  1. text validation - one statement, starts with SELECT/WITH, no write keywords;
  2. a read-only connection opened by the database engine (the real backstop);
  3. a row limit so output stays small enough for the model's context window.

HOW IT FITS: it duplicates the logic of ``src/playbook/sqlguard.py`` ON PURPOSE (that
module needs the ``playbook`` package installed; this file must work when the skill
folder is copied elsewhere).  If you change one validator, change the other - note the
copies already differ slightly (row limit 200 here vs 100 there; ``schema`` here also
lists ``sqlite_*`` internal tables).

Exit codes: 0 success, 1 validation or database error (message on stderr), 2 wrong
number of arguments (usage text printed).

Limitations: textual checks may reject harmless queries containing ``;`` or a word like
"replace" inside a string literal; SQLite only.
"""
from __future__ import annotations

import re
import sqlite3
import sys

# Same forbidden-keyword list as sqlguard: whole words that write data, change schema,
# or alter engine state (attach can open other files; pragma can change settings).
# ``\b`` = word boundary, so "updated_at" is not mistaken for "update".
FORBIDDEN = re.compile(
    r"\b(insert|update|delete|drop|alter|create|replace|truncate|attach|detach|pragma|vacuum|reindex)\b",
    re.IGNORECASE,
)


def validate(sql: str) -> str:
    """Return the cleaned statement or raise ValueError.

    Strips whitespace and one trailing ``;``; rejects any remaining ``;`` (a second,
    smuggled statement); requires the text to start with SELECT or WITH (``^`` start,
    ``\\b`` stops "selection" matching); rejects write keywords anywhere in the text.
    """
    statement = sql.strip().rstrip(";").strip()
    if ";" in statement:
        raise ValueError("only a single statement is allowed")
    if not re.match(r"^(select|with)\b", statement, re.IGNORECASE):
        raise ValueError("only SELECT / WITH queries are allowed")
    if FORBIDDEN.search(statement):
        raise ValueError("statement contains a forbidden keyword")
    return statement


def connect_readonly(path: str) -> sqlite3.Connection:
    """Open ``path`` in SQLite read-only mode so the engine itself rejects any write.

    ``file:...?mode=ro`` is a SQLite URI (hence ``uri=True``); the file must already
    exist.  ``sqlite3.Row`` allows access by column name.  ``?`` or ``#`` in the path
    would corrupt the URI and are not supported.
    """
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def schema(conn: sqlite3.Connection) -> str:
    """Return the CREATE TABLE text of every table, separated by blank lines.

    ``sqlite_master`` is SQLite's built-in catalogue of schema objects.  ``r["sql"]`` can
    be NULL for some internal tables, so the table name is used as a fallback.
    """
    rows = conn.execute("SELECT name, sql FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
    return "\n\n".join(r["sql"] or r["name"] for r in rows)


def run(conn: sqlite3.Connection, sql: str, limit: int = 200) -> list[dict]:
    """Validate and execute ``sql``; return up to ``limit`` rows as dicts.

    ``fetchmany`` reads only the first ``limit`` rows, protecting memory and the
    model's context.  Raises ValueError (validation) or sqlite3.Error (bad SQL).
    """
    cur = conn.execute(validate(sql))
    return [dict(r) for r in cur.fetchmany(limit)]


def main(argv: list[str]) -> int:
    """CLI entry point; ``argv`` is ``sys.argv`` (script name, db path, query/--schema)."""
    # Exactly: script, db path, and one more argument.  Anything else -> show usage
    # (this module's docstring) and return 2, the conventional "bad usage" status.
    if len(argv) != 3:
        print(__doc__)
        return 2
    path, arg = argv[1], argv[2]
    try:
        conn = connect_readonly(path)
        if arg == "--schema":
            print(schema(conn))
        else:
            rows = run(conn, arg)
            if rows:
                # Header line from the first row's column names, then one line per row.
                print(" | ".join(rows[0].keys()))
                for row in rows:
                    print(" | ".join(str(v) for v in row.values()))
            print(f"({len(rows)} rows)")
    except (ValueError, sqlite3.Error) as exc:
        # Errors go to stderr so they are not mistaken for query output.
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
