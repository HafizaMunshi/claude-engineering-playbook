"""Tests for playbook.sqlguard - the read-only SQL guard used by the MCP DB server and tools.

The guard is "defence in depth": (1) a syntactic allow-list, (2) a connection opened
read-only at the SQLite level, (3) a row cap. These tests cover each layer. The SQL comes
from an LLM, so it must be treated as hostile input.

Run: .venv\\Scripts\\python.exe -m pytest tests/test_sqlguard.py -q   (offline, no API key)
"""
import sqlite3

import pytest

from playbook import sqlguard


@pytest.mark.parametrize("sql", [
    "SELECT * FROM customers",
    "  select id from customers;  ",
    "WITH a AS (SELECT 1 x) SELECT x FROM a",
])
def test_accepts_read_only_statements(sql):
    """Legitimate SELECT/WITH queries (any case, spaces, trailing ;) must pass.

    Protects against an over-eager guard that blocks useful queries and makes the tool
    useless. Returns the cleaned statement, which must be truthy.
    """
    assert sqlguard.validate_select(sql)


@pytest.mark.parametrize("sql", [
    "DELETE FROM customers",
    "UPDATE customers SET name='x'",
    "SELECT 1; DROP TABLE customers",
    "INSERT INTO customers VALUES (9,'a','b','c')",
    "PRAGMA writable_schema=1",
    "SELECT * FROM customers WHERE name = 'x' OR 1=1; --",
])
def test_rejects_anything_else(sql):
    """Writes, DDL, PRAGMA, stacked statements and a comment-based injection are refused.

    Each case hits a different rule: forbidden keyword (DELETE/UPDATE/INSERT/PRAGMA),
    multiple statements ("; DROP"), and a trailing "; --" injection that leaves a stray
    semicolon. If any slips through, a prompt-injected model could modify data.
    """
    with pytest.raises(sqlguard.UnsafeSQL):
        sqlguard.validate_select(sql)


def test_connection_is_physically_read_only(sample_db):
    """Layer 2: even bypassing validate_select, SQLite itself refuses to write.

    Calls conn.execute directly (skipping the validator) to prove the connection opened with
    mode=ro. Fails if open_readonly ever opens the file read-write: then a validator bug
    would become data loss.
    """
    conn = sqlguard.open_readonly(str(sample_db))
    with pytest.raises(sqlite3.OperationalError):
        conn.execute("DELETE FROM customers")


def test_finds_the_planted_duplicate(sample_db):
    """End-to-end sanity: run_select returns dict rows and finds the seeded data bug.

    The sample DB deliberately gives customer 2 two active subscriptions; the demos and the
    investigation skill rely on this being discoverable. Breaks if the schema, the seed data
    or the row-to-dict conversion changes.
    """
    conn = sqlguard.open_readonly(str(sample_db))
    rows = sqlguard.run_select(
        conn, "SELECT customer_id, COUNT(*) n FROM subscriptions WHERE status='active' "
              "GROUP BY customer_id HAVING n > 1")
    assert rows == [{"customer_id": 2, "n": 2}]


def test_row_cap(sample_db):
    """Layer 3: max_rows truncates results (2 of 4 customers here).

    Protects the model's context window from a careless SELECT * on a huge table. Fails if
    the cap is ignored.
    """
    conn = sqlguard.open_readonly(str(sample_db))
    assert len(sqlguard.run_select(conn, "SELECT * FROM customers", max_rows=2)) == 2
