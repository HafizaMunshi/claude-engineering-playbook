"""Tests for playbook.tools: the safe calculator, tool dispatch and the hand-written agent loop.

The Messages API tool contract being protected: the model asks for tools (stop_reason
"tool_use"), we run EVERY requested tool, and we send ALL results back in ONE user message
with matching tool_use_id values, repeating until the model answers. FakeClient (conftest.py)
scripts the model's side so no network is needed.

Run: .venv\\Scripts\\python.exe -m pytest tests/test_tools.py -q
"""
import json

import pytest

from conftest import text_response, tool_response
from playbook import sqlguard
from playbook.tools import execute_tool, make_toolset, run_agent_loop, safe_eval


@pytest.mark.parametrize("expr,expected", [("2+3*4", 14), ("(19*49)/100", 9.31), ("-5+2", -3), ("2**10", 1024)])
def test_safe_eval(expr, expected):
    """The calculator evaluates normal arithmetic (precedence, parens, unary minus, powers).

    approx() because 9.31 is a float result. Fails if the AST walker mishandles an operator.
    """
    assert safe_eval(expr) == pytest.approx(expected)


@pytest.mark.parametrize("expr", ["__import__('os').system('echo hi')", "open('x')", "1; 2", "abs(-1)"])
def test_safe_eval_rejects_code(expr):
    """Model-supplied "expressions" that are really code must be rejected, never executed.

    Covers import/exec injection, a function call, two statements (SyntaxError) and even
    harmless abs(-1) (calls are not whitelisted). If safe_eval were replaced by eval(), the
    first case would run a shell command - this test is the guard against that regression.
    """
    with pytest.raises((ValueError, SyntaxError)):
        safe_eval(expr)


def test_execute_tool_reports_errors_instead_of_raising():
    """Tool failures and unknown tool names become (message, is_error=True), not exceptions.

    The error text goes back to the model so it can recover; an exception here would crash
    the whole agent loop on one bad tool call.
    """
    content, is_error = execute_tool({"boom": lambda a: 1 / 0}, "boom", {})
    assert is_error and "ZeroDivisionError" in content
    assert execute_tool({}, "nope", {}) == ("Unknown tool: nope", True)


def test_agent_loop_runs_parallel_tools_and_returns_all_results_in_one_message(sample_db, fake):
    """Two tool_use blocks in one turn -> both run -> ONE user message with TWO tool_results.

    The API rejects (or the model gets confused by) results split across messages or with
    mismatched ids, so this checks: single message, role "user", ids in order t1,t2, and that
    the DB result is real JSON ([{"c": 4}], four sample customers). Script: turn 1 tools,
    turn 2 final text.
    """
    conn = sqlguard.open_readonly(str(sample_db))
    tools, handlers = make_toolset(conn)
    client = fake(create=[
        tool_response(("t1", "calculator", {"expression": "49*2"}),
                      ("t2", "query_database", {"sql": "SELECT COUNT(*) c FROM customers"})),
        text_response("Done: 98 and 4 customers."),
    ])
    answer = run_agent_loop(client, "go", tools, handlers)

    assert answer == "Done: 98 and 4 customers."
    # The second API request carries the history; its last entry is our tool-results message.
    second_request = client.messages.create_calls[1]["messages"]
    results = second_request[-1]["content"]
    assert second_request[-1]["role"] == "user" and len(results) == 2          # one message, two results
    assert [r["tool_use_id"] for r in results] == ["t1", "t2"]
    assert json.loads(results[1]["content"]) == [{"c": 4}]


def test_agent_loop_feeds_unsafe_sql_back_as_error(sample_db, fake):
    """A prompt-injected DROP TABLE is blocked by the guard and reported as is_error.

    Proves the whole chain (loop -> execute_tool -> sqlguard) fails safe: the DB is untouched
    and the model is told why (message mentions SELECT) so it can answer sensibly.
    """
    tools, handlers = make_toolset(sqlguard.open_readonly(str(sample_db)))
    client = fake(create=[tool_response(("t1", "query_database", {"sql": "DROP TABLE customers"})),
                          text_response("I cannot do that.")])
    run_agent_loop(client, "drop it", tools, handlers)
    result = client.messages.create_calls[1]["messages"][-1]["content"][0]
    assert result["is_error"] is True and "SELECT" in result["content"]


def test_agent_loop_is_bounded(fake):
    """A model that asks for tools forever must be cut off after max_turns.

    The callable responder returns a tool request every time. Without the bound the loop
    would burn tokens/money indefinitely; the final message must mention "3 turns".
    """
    forever = lambda kw: tool_response(("t", "calculator", {"expression": "1+1"}))  # noqa: E731
    _, handlers = make_toolset(None)  # calculator needs no DB
    # tools=[] is fine here: the fake client ignores the schemas, only handlers matter.
    out = run_agent_loop(fake(create=forever), "x", [], handlers, max_turns=3)
    assert "3 turns" in out
