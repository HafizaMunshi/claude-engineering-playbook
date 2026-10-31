#!/usr/bin/env python3
"""Concept: Messages API basics - system prompt, multi-turn state, usage accounting.

WHAT IT SHOWS
    A tiny `Conversation` class that holds a chat history and calls `messages.create`
    once per user turn. The demo asks a question, then a follow-up that only makes
    sense if the model "remembers" the first answer.

COURSE CONCEPT (Building with the Claude API: making requests)
    The API is STATELESS. The server keeps no memory between calls, so YOU resend the
    whole conversation (every earlier user and assistant message) on every request.
    This matters in real work because (a) context is what you pay for - input tokens
    grow with every turn - and (b) you decide what the model remembers, so you can
    trim, summarise or edit history yourself.
    Also note: current models reject temperature/top_p/top_k, so this repo steers
    behaviour with the system prompt (and `output_config.effort`, see example 08)
    rather than sampling parameters. That is why no temperature is passed below.

HOW TO RUN (from the repo root, after `pip install -e ".[dev]"`)
    export ANTHROPIC_API_KEY=...        # Windows PowerShell: $env:ANTHROPIC_API_KEY="..."
    python examples/api/01_first_message.py
    Optional: CLAUDE_MODEL overrides the model id (see playbook.common.model).

EXPECTED OUTPUT
    Two short (at most 3 sentence) answers: first mutex vs semaphore, then a one-line
    example of choosing a semaphore. The last line prints cumulative token counts as
    `tokens in/out: <input>/<output>`; the input number grows faster than the output
    because turn 2 re-sends turn 1 as context.

REPO MODULES USED
    playbook.common: get_client() (builds the SDK client from the environment),
    model() (default model id, overridable by env var) and text_of() (joins text blocks).

GOTCHAS / TRY NEXT
    * The history stores only the reply TEXT. That is fine for plain chat, but once
      tools or thinking are involved you must append the full content blocks (example 04).
    * Try removing the system prompt and see the answers get longer.
    * Next: example 02 streams the same kind of request token by token.
"""
from playbook.common import get_client, model, text_of


class Conversation:
    """A minimal stateful wrapper around a stateless API.

    Holds the system prompt, the running message list and token totals. The caller
    only ever calls `say()`; this class takes care of resending the history.
    """

    def __init__(self, client, system: str):
        """Store the SDK client and system prompt and start with an empty history.

        Args:
            client: an `anthropic.Anthropic` instance (passed in so tests can inject a fake).
            system: instructions that apply to the whole conversation (role, style, limits).
        """
        self.client, self.system, self.messages = client, system, []
        # Running totals across all turns, for a rough cost picture.
        self.input_tokens = self.output_tokens = 0

    def say(self, user_text: str) -> str:
        """Send one user turn, record the reply, and return the reply text.

        Args:
            user_text: what the user says this turn.

        Returns:
            The assistant's reply as plain text (all text blocks concatenated).
        """
        # `messages` is a list of {"role", "content"} dicts. Role "user" is the human
        # side; role "assistant" is the model. They must alternate, starting with user.
        self.messages.append({"role": "user", "content": user_text})
        response = self.client.messages.create(
            # model: which Claude model answers (cost/quality/latency trade-off).
            # max_tokens: hard cap on OUTPUT tokens for this call (required by the API);
            #   if the reply would be longer it is cut off and stop_reason == "max_tokens".
            # system: top-level instructions; it is a separate parameter, NOT a message role.
            # messages: the FULL history so far - this is how "memory" works.
            model=model(), max_tokens=1500, system=self.system, messages=self.messages)
        # A response's `content` is a list of blocks (text, thinking, tool_use...).
        # text_of() joins the text blocks into one string.
        reply = text_of(response)
        # Save the reply so the next call includes it; without this the follow-up
        # question would have no context.
        self.messages.append({"role": "assistant", "content": reply})
        # `usage` reports what this call was billed for. input_tokens counts the whole
        # resent history, so it grows each turn; output_tokens is just the new reply.
        self.input_tokens += response.usage.input_tokens
        self.output_tokens += response.usage.output_tokens
        return reply


if __name__ == "__main__":
    chat = Conversation(get_client(), system="You are a staff engineer. Answer in at most 3 sentences.")
    print(chat.say("What is the difference between a mutex and a semaphore?"))
    print(chat.say("Give a one-line example of when I'd pick the second one."))  # relies on turn 1
    print(f"tokens in/out: {chat.input_tokens}/{chat.output_tokens}")
