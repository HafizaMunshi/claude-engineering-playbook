"""Shared test doubles: a scripted fake Anthropic client so every test runs offline.

WHAT THIS FILE IS
  pytest automatically loads conftest.py before the tests in this folder. It provides
  (1) helpers that build fake API responses, (2) FakeClient, a stand-in for the Anthropic
  client, and (3) fixtures `fake` and `sample_db` that tests receive by naming them as
  function parameters. test_tools.py also imports text_response/tool_response directly.

WHY A FAKE CLIENT INSTEAD OF unittest.mock
  The code under test (playbook.tools, workflows, evals, rag) only ever calls
  `client.messages.create(...)` and `client.messages.parse(...)`. A small hand-written fake:
    * is readable: a test states the model's replies up front as plain data;
    * is strict: running out of scripted replies raises IndexError, so a code path that makes
      more API calls than expected fails loudly (a MagicMock would silently return mocks);
    * records every call's kwargs (create_calls / parse_calls) so tests can assert on what
      was SENT - the system prompt, the message history - not just what came back;
    * needs no API key or network, so the suite is fast, free and deterministic.
  This works because the library functions take a `client` argument (dependency
  injection) instead of building one internally.

HOW A RESPONDER WORKS: LIST vs CALLABLE
  Each of create= and parse= is either
    * a list: replies consumed in order (pop(0)) - "first call gets A, second gets B".
      Use when the order of calls is deterministic.
    * a callable taking the call's kwargs and returning the reply - use when the reply
      depends on the request, or when calls happen concurrently so order is not
      deterministic (e.g. the parallel reviews in workflows.parallelize), or when the same
      reply must repeat forever (the bounded-loop test).
  For create(), a plain str reply is auto-wrapped into a text response for convenience.
  For parse(), the reply is wrapped as `.parsed_output` (a Pydantic model instance), which
  mirrors the real structured-output API.

WHY THERE IS A LOCK
  workflows.parallelize runs several calls in a ThreadPoolExecutor, so create() can be
  invoked from several threads at once. list.append / list.pop(0) are individually safe in
  CPython but the pair "record call, then take next reply" and the list consumption should
  not interleave unpredictably; the lock keeps the recorded calls and consumed replies
  consistent. Callable responders are run OUTSIDE the lock on purpose so a slow or
  re-entrant callable cannot deadlock the fake.
"""
from __future__ import annotations

import threading
from types import SimpleNamespace
from typing import Any, Callable

import pytest


def text_response(text: str, stop_reason: str = "end_turn") -> SimpleNamespace:
    # Mimics the few fields the code reads from a Messages API response: content blocks with
    # .type/.text, .stop_reason (end_turn = model is finished) and .usage token counts.
    # SimpleNamespace gives attribute access without importing the real SDK types.
    return SimpleNamespace(content=[SimpleNamespace(type="text", text=text)], stop_reason=stop_reason,
                           usage=SimpleNamespace(input_tokens=1, output_tokens=1))


def tool_response(*calls: tuple[str, str, dict]) -> SimpleNamespace:
    # Each call is (tool_use_id, tool_name, input_dict). Several calls in one response model
    # the model requesting parallel tool use. stop_reason="tool_use" is the signal that makes
    # the agent loop execute the tools and continue instead of returning.
    blocks = [SimpleNamespace(type="tool_use", id=i, name=n, input=a) for i, n, a in calls]
    return SimpleNamespace(content=blocks, stop_reason="tool_use",
                           usage=SimpleNamespace(input_tokens=1, output_tokens=1))


class _Messages:
    """Fake of `client.messages`: scripted replies in, recorded calls out."""

    def __init__(self, create: Callable | list, parse: Callable | list):
        self._create, self._parse = create, parse  # each is a list OR a callable (see above)
        # Recorded kwargs of every call. Caveat: these hold REFERENCES, so if the code under
        # test later mutates e.g. its `messages` list, an earlier recorded call shows the
        # mutated list too. Assertions are written with that in mind.
        self.create_calls: list[dict] = []
        self.parse_calls: list[dict] = []
        self._lock = threading.Lock()

    def _next(self, source: Callable | list, kwargs: dict) -> Any:
        """Produce the next scripted reply from either kind of responder."""
        if callable(source):
            return source(kwargs)
        with self._lock:
            return source.pop(0)  # IndexError here = the code made more calls than scripted

    def create(self, **kwargs: Any) -> Any:
        """Stand-in for messages.create(): free-form text / tool-use responses."""
        with self._lock:
            self.create_calls.append(kwargs)
        result = self._next(self._create, kwargs)
        return text_response(result) if isinstance(result, str) else result

    def parse(self, **kwargs: Any) -> Any:
        """Stand-in for messages.parse(): structured output returned as .parsed_output."""
        with self._lock:
            self.parse_calls.append(kwargs)
        return SimpleNamespace(parsed_output=self._next(self._parse, kwargs))


class FakeClient:
    """Drop-in for anthropic.Anthropic in tests: only `.messages.create/parse` exist.

    Usage: FakeClient(create=["reply1", "reply2"]) or FakeClient(parse=[SomeModel(...)]).
    Inspect `client.messages.create_calls` afterwards to assert on what was sent.
    """

    def __init__(self, create: Callable | list | None = None, parse: Callable | list | None = None):
        self.messages = _Messages(create or [], parse or [])


@pytest.fixture
def fake():
    # Returns the CLASS, not an instance, so each test builds its own scripted client:
    # `client = fake(create=[...])`. Keeps scripts local to the test that needs them.
    return FakeClient


@pytest.fixture
def sample_db(tmp_path):
    # A fresh synthetic SQLite file per test in pytest's temp dir (auto-cleaned), so tests
    # never share or corrupt state. Returns the Path. Contains the planted bug: customer 2 has
    # two ACTIVE subscriptions. Import is inside the fixture so collection stays cheap.
    from playbook import sampledb
    return sampledb.build(tmp_path / "sample.sqlite")
