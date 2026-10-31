"""Read-only SQL guard shared by the MCP DB server and the tool-use examples.

WHAT: functions that accept SQL text (which may come from an LLM, i.e. UNTRUSTED
input), check that it is a single read-only query, and run it on a read-only SQLite
connection with a row cap.

WHY: letting a model write SQL is useful for data investigation but dangerous if it
can modify data.  This file demonstrates the course principle "tool inputs are
untrusted: validate before executing".

Defence in depth: (1) syntactic allow-list, (2) read-only connection,
(3) row cap so a careless query cannot flood the model's context.

Each layer is deliberately redundant.  The regex checks are a heuristic that can be
fooled or can reject harmless queries; the read-only connection is the real backstop
that the database itself enforces; the row cap protects the context window.

HOW IT FITS: ``tools.make_toolset`` wraps ``run_select`` / ``describe_schema`` as model
tools, and ``examples/mcp/db_server.py`` exposes them over MCP.  The skill script
``.claude/skills/readonly-db-investigation/scripts/safe_query.py`` is a standalone,
stdlib-only copy of the same idea (kept separate so the skill folder is portable).

Usage:
    conn = open_readonly("examples/mcp/sample.sqlite")   # see sampledb.build()
    rows = run_select(conn, "SELECT * FROM customers")

Known limitations:
  * The checks are textual: a ``;`` or a word like "replace" INSIDE a string literal
    (e.g. ``WHERE note = 'a;b'``) is rejected as a false positive.
  * Only SQLite is supported.
"""
from __future__ import annotations

import re
import sqlite3

# Matches any keyword that writes data, changes schema, or changes engine state.
#   \b(...)\b      - whole words only, so a column called "updated_at" does NOT match
#                    "update" (no word boundary inside "updated").
#   ... | pragma   - PRAGMA can change settings / write (e.g. writable_schema).
#   ... | attach   - ATTACH DATABASE could open or create ANOTHER file on disk.
#   re.IGNORECASE  - "DrOp" must be caught too.
_FORBIDDEN = re.compile(
    r"\b(insert|update|delete|drop|alter|create|replace|truncate|attach|detach|pragma|vacuum|reindex)\b",
    re.IGNORECASE,
)
# Maximum rows returned to the caller; protects the model's context window.
MAX_ROWS = 100


class UnsafeSQL(ValueError):
    """Raised when a statement is not a single read-only SELECT."""


def validate_select(sql: str) -> str:
    """Check ``sql`` is one read-only SELECT/WITH statement and return it cleaned.

    Checks, in order:
      1. Strip whitespace and ONE trailing ``;`` (models often add it).
      2. Any remaining ``;`` means a second statement (stacked-query injection such
         as a SELECT followed by a DROP) -> rejected.
      3. Must START with SELECT or WITH (common table expression).  Regex pieces:
         ``^`` start of text, ``(select|with)`` either word, ``\\b`` word boundary so
         "selection" or "withdraw" do not pass.
      4. Must not contain a forbidden keyword anywhere (stops e.g. a data-modifying
         statement hidden inside a WITH clause).

    Returns:
        The cleaned statement (no surrounding space, no trailing semicolon).
    Raises:
        UnsafeSQL: if any check fails (message says which).
    """
    statement = sql.strip().rstrip(";").strip()
    if ";" in statement:
        raise UnsafeSQL("only one statement is allowed")
    if not re.match(r"^(select|with)\b", statement, re.IGNORECASE):
        raise UnsafeSQL("only SELECT or WITH queries are allowed")
    if _FORBIDDEN.search(statement):
        raise UnsafeSQL("statement contains a forbidden keyword")
    return statement


def open_readonly(path: str) -> sqlite3.Connection:
    """Open a SQLite file so the DATABASE ENGINE refuses all writes.

    ``mode=ro`` in a SQLite URI opens the file read-only; any INSERT/UPDATE/DDL then
    fails with an error even if our regex checks were somehow bypassed.  ``uri=True``
    is required for SQLite to interpret the ``file:...?mode=ro`` form.  The file must
    already exist (read-only mode will not create it).  ``row_factory = sqlite3.Row``
    lets rows be accessed by column name and converted with ``dict(row)``.

    Note: ``path`` is placed into a URI unescaped, so paths containing ``?`` or ``#``
    are not supported.
    """
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def run_select(conn: sqlite3.Connection, sql: str, max_rows: int = MAX_ROWS) -> list[dict]:
    """Validate then execute ``sql``; return at most ``max_rows`` rows as dicts.

    Raises ``UnsafeSQL`` (from validation) or ``sqlite3.Error`` (bad SQL / missing
    table).  ``fetchmany`` pulls only the first ``max_rows`` rows from the cursor, so
    a huge result set is never fully materialised in Python memory.
    """
    cursor = conn.execute(validate_select(sql))
    return [dict(row) for row in cursor.fetchmany(max_rows)]


def describe_schema(conn: sqlite3.Connection) -> dict[str, list[str]]:
    """Return ``{table_name: ["column TYPE", ...]}`` for every user table.

    Lets the model discover table/column names before writing a query, so it does not
    have to guess.  Internal ``sqlite_*`` tables are excluded.  ``PRAGMA table_info``
    returns one row per column with fields ``name`` and ``type``; the table name is
    wrapped in double quotes (SQL identifier quoting) because a PRAGMA argument cannot
    be a bound parameter.  The names come from the database itself, not from the model.
    (PRAGMA is allowed here because this is our own fixed code, not model input.)
    """
    tables = [r["name"] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
    return {t: [c["name"] + " " + c["type"] for c in conn.execute(f'PRAGMA table_info("{t}")')] for t in tables}
