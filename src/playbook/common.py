"""Tiny helpers shared by every example.

WHAT: model-id lookup, an Anthropic client factory, and two convenience functions
(``text_of`` and ``ask``) that turn a Messages API response into plain text.

WHY: every example needs the same few things, so they live here once.  It also
demonstrates the course advice to keep configuration (credentials, model ids) out of
source code and in the environment.

HOW IT FITS: ``workflows``, ``evals``, ``rag`` and ``tools`` import from this module.
Nothing here imports from the rest of ``playbook``, so there are no import cycles.

Design rules used across the repo:
  * Credentials come from the environment (ANTHROPIC_API_KEY) - never hardcoded.
  * Model ids come from env vars so examples never go stale.
  * Every example exposes pure functions that accept a ``client`` so tests can
    inject a fake and run offline.

Usage:
    from playbook.common import get_client, ask
    print(ask(get_client(), "Say hello"))      # needs ANTHROPIC_API_KEY

Gotcha: the default model ids below are only defaults.  If a model is retired, set
CLAUDE_MODEL / CLAUDE_FAST_MODEL in the environment instead of editing examples.
"""
from __future__ import annotations

import os
from typing import Any

import anthropic

# Two "tiers" of model: a large one for hard reasoning / multi-step agent work and a
# small, cheap, low-latency one for simple jobs (classification, routing, grading).
# Picking the cheapest model that is good enough is a core cost-control habit.
DEFAULT_MODEL = "claude-opus-5-5"      # heavy reasoning / agentic work
DEFAULT_FAST_MODEL = "claude-haiku-5-5"  # cheap classification / routing


def model() -> str:
    """Return the id of the main (high-capability) model.

    Reads ``CLAUDE_MODEL`` from the environment at CALL time (not import time), so a
    test or script can change it with ``monkeypatch.setenv`` / ``os.environ`` and see
    the new value immediately.  Falls back to ``DEFAULT_MODEL``.
    """
    return os.environ.get("CLAUDE_MODEL", DEFAULT_MODEL)


def fast_model() -> str:
    """Return the id of the small/cheap model (override with ``CLAUDE_FAST_MODEL``)."""
    return os.environ.get("CLAUDE_FAST_MODEL", DEFAULT_FAST_MODEL)


def get_client() -> anthropic.Anthropic:
    """Zero-arg client: resolves ANTHROPIC_API_KEY (or a logged-in profile).

    The SDK reads the key from the environment itself, so no secret ever appears in
    this repo.  Tests never call this; they pass a fake client to the functions that
    need one.
    """
    return anthropic.Anthropic()


def text_of(response: Any) -> str:
    """Concatenate the text blocks of a Messages response.

    A Messages API response's ``content`` is a LIST of typed blocks, not a string:
    e.g. ``text`` blocks, ``tool_use`` blocks, ``thinking`` blocks.  This helper keeps
    only the ``text`` ones and joins them.  ``getattr(b, "type", "")`` is used so a
    block lacking a ``type`` attribute is skipped instead of raising.

    Args:
        response: the object returned by ``client.messages.create`` (or a test fake).
    Returns:
        The joined text, or "" if the response held no text blocks.
    """
    return "".join(b.text for b in response.content if getattr(b, "type", "") == "text")


def ask(client: anthropic.Anthropic, prompt: str, *, system: str | None = None,
        max_tokens: int = 2000, use_fast: bool = False, **extra: Any) -> str:
    """One-shot helper: a single user prompt in, plain text out.

    Args:
        client: an Anthropic client (or a test fake with the same ``messages.create``).
        prompt: the user message.
        system: optional system prompt (standing instructions / persona for the model).
        max_tokens: hard cap on the length of the reply, in tokens.  The API requires it.
        use_fast: use the cheap model (``fast_model()``) instead of ``model()``.
        **extra: any other ``messages.create`` argument, passed straight through.
    Returns:
        The reply as plain text (see ``text_of``).
    """
    kwargs: dict[str, Any] = dict(
        model=fast_model() if use_fast else model(),
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
        **extra,
    )
    # ``system`` is a separate top-level parameter in the Messages API (it is NOT a
    # message with role "system"), and it is only sent when provided.
    if system:
        kwargs["system"] = system
    return text_of(client.messages.create(**kwargs))
