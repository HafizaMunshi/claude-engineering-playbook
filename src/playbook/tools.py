"""Tool use, done by hand: schemas, a safe dispatcher, and the agentic loop.

WHAT: three example tools (calculator, describe_schema, query_database), a function
that runs a tool safely, and ``run_agent_loop`` - the loop that lets Claude call
tools until it has a final answer.

WHY: this is the "Building with the Claude API" tool-use lesson written out manually
instead of using the SDK's tool runner (compare ``examples/api/05_*``).  Writing the
loop yourself shows exactly what the API contract is.

Teaches the contract of the Messages API tool loop:
  1. send ``tools`` + messages
  2. if ``stop_reason == "tool_use"``: run EVERY tool_use block
  3. return ALL results in ONE user message (tool_use_id must match)
  4. repeat until the model stops asking for tools

Vocabulary used below:
  * tool schema   - a JSON description (name, description, JSON-Schema ``input_schema``)
                    telling the model what a tool does and what arguments it takes.
  * tool_use      - a content block in the model's reply: "please call tool X with args Y".
                    The MODEL never runs anything; YOUR code does and reports back.
  * tool_result   - the content block you send back, matched to the request by id.
  * stop_reason   - why generation ended: "end_turn" (finished), "tool_use" (wants a
                    tool), "max_tokens" (hit the length cap), "refusal", ...

HOW IT FITS: database tools delegate to ``sqlguard`` (read-only by construction);
the model id comes from ``common``.  Tests drive the loop with a scripted fake client
(see ``tests/test_tools.py``).

Security stance: tool arguments come from a model that may have read hostile text, so
they are UNTRUSTED.  The calculator therefore parses an AST instead of calling
``eval``, and SQL goes through the guard.
"""
from __future__ import annotations

import ast
import json
import operator
import sqlite3
from typing import Any, Callable

from playbook import sqlguard
from playbook.common import model as default_model

# A handler takes the model-supplied argument dict and returns any JSON-serialisable value.
Handler = Callable[[dict[str, Any]], Any]

# ---------------------------------------------------------------- calculator
# Allow-list mapping AST operator node types to the real Python function that does the
# maths.  Anything not listed here (function calls, attribute access, names, ...) is
# rejected by ``safe_eval``.
_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
        ast.Div: operator.truediv, ast.Pow: operator.pow, ast.USub: operator.neg, ast.Mod: operator.mod}


def safe_eval(expression: str) -> float:
    """Evaluate arithmetic only. Never use eval() on model-provided input.

    ``eval("__import__('os').system(...)")`` would run arbitrary code, so instead we
    PARSE the text into a syntax tree (``ast.parse``) and evaluate only node types we
    explicitly allow: numeric constants, binary operators in ``_OPS`` and unary minus.

    Args:
        expression: e.g. ``"(19 * 49) / 100"``.
    Returns:
        The numeric result.
    Raises:
        ValueError: for any unsupported construct.
        SyntaxError: if the text is not valid Python expression syntax.
        ZeroDivisionError: on division by zero.
    Known limitation: ``**`` is allowed, so a huge power such as ``9 ** 9 ** 9`` could
    consume CPU/memory; there is no exponent limit.
    """
    def walk(node: ast.AST) -> float:
        # A literal number such as 19 or 4.5.
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        # "left <op> right": recurse into both sides, then apply the allowed operator.
        if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
            return _OPS[type(node.op)](walk(node.left), walk(node.right))
        # A prefix operator such as -5 (the only unary operator in the allow-list).
        if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
            return _OPS[type(node.op)](walk(node.operand))
        raise ValueError("unsupported expression")
    # mode="eval" accepts exactly one expression (no statements); ``.body`` is its root node.
    return walk(ast.parse(expression, mode="eval").body)


# ------------------------------------------------------------- tool schemas
# ``"strict": True`` asks the API to guarantee the model's arguments match the schema
# exactly; ``additionalProperties: False`` forbids invented extra arguments.  Validation
# in our handlers is still required - the schema is a guide, not a security boundary.
CALCULATOR_TOOL = {
    "name": "calculator",
    "description": "Evaluate an arithmetic expression (+ - * / ** %). Use for any exact maths.",
    "strict": True,
    "input_schema": {
        "type": "object",
        "properties": {"expression": {"type": "string", "description": "e.g. '(19 * 49) / 100'"}},
        "required": ["expression"],
        "additionalProperties": False,
    },
}

# The description is itself prompt text: it tells the model the limits (one SELECT,
# 100 rows) and what to do first (look at the schema), which reduces wasted turns.
QUERY_TOOL = {
    "name": "query_database",
    "description": ("Run ONE read-only SELECT against the application database and return rows as JSON "
                    "(max 100). Inspect the schema with describe_schema first."),
    "strict": True,
    "input_schema": {
        "type": "object",
        "properties": {"sql": {"type": "string", "description": "A single SELECT statement"}},
        "required": ["sql"],
        "additionalProperties": False,
    },
}

# A tool with no arguments still needs an (empty) object schema.
SCHEMA_TOOL = {
    "name": "describe_schema",
    "description": "List tables and their columns in the application database.",
    "strict": True,
    "input_schema": {"type": "object", "properties": {}, "required": [], "additionalProperties": False},
}


def make_toolset(conn: sqlite3.Connection) -> tuple[list[dict], dict[str, Handler]]:
    """Return (tool schemas, handlers) bound to a READ-ONLY connection.

    The two halves go to different places: the schema list is sent to the API, the
    handler dict (name -> Python callable) stays local and is used by ``execute_tool``.
    Callers should pass a connection from ``sqlguard.open_readonly`` so that even a
    bug in the SQL validator cannot modify data.
    """
    handlers: dict[str, Handler] = {
        "calculator": lambda args: safe_eval(args["expression"]),
        "describe_schema": lambda args: sqlguard.describe_schema(conn),
        "query_database": lambda args: sqlguard.run_select(conn, args["sql"]),
    }
    return [CALCULATOR_TOOL, SCHEMA_TOOL, QUERY_TOOL], handlers


def execute_tool(handlers: dict[str, Handler], name: str, args: dict[str, Any]) -> tuple[str, bool]:
    """Run one tool. Returns (content, is_error). Errors go BACK to the model, not up the stack.

    Why not let exceptions propagate?  A bad query or unknown tool is a normal event in
    an agent loop.  Returning the error text with ``is_error=True`` lets the model read
    it and try again (self-correction) instead of crashing the whole run.

    ``json.dumps(..., default=str)`` converts values JSON cannot represent (dates,
    Decimals, bytes...) to strings rather than failing.
    """
    handler = handlers.get(name)
    if handler is None:
        # The model asked for a tool we never offered (or mis-spelled the name).
        return f"Unknown tool: {name}", True
    try:
        return json.dumps(handler(args), default=str), False
    except Exception as exc:  # noqa: BLE001 - the model should see and recover from any tool failure
        return f"{type(exc).__name__}: {exc}", True


def run_agent_loop(client: Any, prompt: str, tools: list[dict], handlers: dict[str, Handler], *,
                   system: str | None = None, max_turns: int = 8, model: str | None = None,
                   on_event: Callable[[str], None] | None = None) -> str:
    """Manual agentic loop. Bounded by ``max_turns`` so a confused model cannot spin forever.

    Args:
        client: Anthropic client (or a scripted fake in tests).
        prompt: the first user message.
        tools / handlers: from ``make_toolset`` (schemas to send, callables to run).
        system: optional system prompt.
        max_turns: maximum number of API calls (each "turn" is one request/response).
        model: override the model id; defaults to ``common.model()``.
        on_event: optional callback receiving one human-readable log line per event
            (used by demos to print progress; ignored if None).
    Returns:
        The model's final text, or the string "Stopped after N turns without a final
        answer." if the turn budget ran out (callers/tests rely on that exact text).
    """
    log = on_event or (lambda _msg: None)
    # The conversation so far.  The API is stateless: we resend the full history on
    # every call, which is why we keep appending to this list.
    messages: list[dict[str, Any]] = [{"role": "user", "content": prompt}]
    for turn in range(1, max_turns + 1):
        kwargs: dict[str, Any] = dict(model=model or default_model(), max_tokens=4096,
                                      tools=tools, messages=messages)
        if system:
            kwargs["system"] = system
        response = client.messages.create(**kwargs)

        # Anything other than "tool_use" means the model is done (or was cut off), so
        # return its text.  Cut-offs are logged because the text may be incomplete.
        if response.stop_reason != "tool_use":
            if response.stop_reason in ("max_tokens", "refusal"):
                log(f"turn {turn}: stopped with {response.stop_reason}")
            return "".join(b.text for b in response.content if b.type == "text")

        # The assistant's turn (including its tool_use blocks) must be echoed back into
        # the history, otherwise the later tool_result would reference an unknown id.
        messages.append({"role": "assistant", "content": response.content})
        results = []
        # The model may request several tools in one turn (parallel tool calls); run
        # every one of them.
        for block in (b for b in response.content if b.type == "tool_use"):
            content, is_error = execute_tool(handlers, block.name, block.input)
            log(f"turn {turn}: {block.name}({block.input}) -> {'ERROR ' if is_error else ''}{content[:80]}")
            # ``tool_use_id`` ties this result to the request that produced it.
            results.append({"type": "tool_result", "tool_use_id": block.id,
                            "content": content, "is_error": is_error})
        messages.append({"role": "user", "content": results})  # ALL results in one message
    return f"Stopped after {max_turns} turns without a final answer."
