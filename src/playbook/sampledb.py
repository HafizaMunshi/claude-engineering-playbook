"""Builds a small, fully synthetic SQLite database used by the DB-related demos.

WHAT: creates a SQLite file with three tables (customers, subscriptions, invoices)
filled with made-up rows.

WHY: the database-investigation demos (tool use, MCP server, the read-only DB skill)
need something to query.  Keeping the data synthetic means the repo never contains
real customer data.

It deliberately contains one data-quality bug (a customer with two *active*
subscriptions) so the investigation examples have something real to find.  Customer 2
("Birch & Co") has subscriptions 2 and 3 both ``active``; a correct system would allow
only one active subscription per customer.

HOW IT FITS: the file is queried through ``sqlguard.open_readonly`` and the tools in
``tools.py``.  Generated ``.sqlite`` files are git-ignored (never commit them).

Usage:
    python -m playbook.sampledb          # writes examples/mcp/sample.sqlite
    from playbook.sampledb import build; build("some/path.sqlite")

Gotcha: ``build`` DELETES any existing file at the target path first.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

# DDL (table definitions).  Notes on the constraints:
#   * ``REFERENCES customers(id)`` declares a foreign key.  SQLite does not enforce
#     foreign keys unless ``PRAGMA foreign_keys=ON`` is set, which this script does not
#     do, so it is documentation here.
#   * The CHECK on ``status`` rejects any value other than the two listed.
#   * The schema has NO unique constraint on active subscriptions per customer - that
#     missing rule is exactly what lets the planted bug exist.
#   * Money is stored as integer cents to avoid floating-point rounding errors.
SCHEMA = """
CREATE TABLE customers (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    country TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE subscriptions (
    id INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL REFERENCES customers(id),
    plan TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('active', 'cancelled')),
    started_at TEXT NOT NULL
);
CREATE TABLE invoices (
    id INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL REFERENCES customers(id),
    amount_cents INTEGER NOT NULL,
    issued_at TEXT NOT NULL
);
"""

# Row tuples follow the column order of the tables above.  Dates are ISO-8601 text
# (SQLite has no dedicated date type).
CUSTOMERS = [
    (1, "Acme Labs", "DE", "2025-01-10"),
    (2, "Birch & Co", "US", "2025-02-14"),
    (3, "Cobalt Works", "IN", "2025-03-02"),
    (4, "Delta Foods", "US", "2025-03-21"),
]
SUBSCRIPTIONS = [
    (1, 1, "pro", "active", "2025-01-10"),
    (2, 2, "basic", "active", "2025-02-14"),
    (3, 2, "pro", "active", "2025-06-01"),  # BUG: second active subscription
    (4, 3, "basic", "cancelled", "2025-03-02"),
    (5, 4, "pro", "active", "2025-03-21"),
]
INVOICES = [
    (1, 1, 4900, "2025-02-01"),
    (2, 2, 1900, "2025-03-01"),
    (3, 2, 4900, "2025-07-01"),
    (4, 4, 4900, "2025-04-01"),
]


def build(path: str | Path) -> Path:
    """Create (or recreate) the sample database at ``path``.

    Missing parent folders are created.  An existing file at ``path`` is deleted so the
    result is always a clean, known state.  Returns the path as a ``Path``.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    conn = sqlite3.connect(path)
    try:
        # executescript runs several ;-separated statements; the "?" placeholders in
        # executemany are bound parameters (never build SQL by string formatting).
        conn.executescript(SCHEMA)
        conn.executemany("INSERT INTO customers VALUES (?,?,?,?)", CUSTOMERS)
        conn.executemany("INSERT INTO subscriptions VALUES (?,?,?,?,?)", SUBSCRIPTIONS)
        conn.executemany("INSERT INTO invoices VALUES (?,?,?,?)", INVOICES)
        conn.commit()
    finally:
        # Always close, even if an insert fails, so the file is not left locked.
        conn.close()
    return path


if __name__ == "__main__":
    # Path is relative to the CURRENT working directory, so run from the repo root.
    print(build("examples/mcp/sample.sqlite"))
