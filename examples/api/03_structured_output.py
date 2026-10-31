#!/usr/bin/env python3
"""Concept: structured data extraction with a schema the API enforces (no regex-parsing of prose).

WHAT IT SHOWS
    A messy, informal chat message is turned into a typed `BugReport` object (title,
    severity, component, repro steps, needs-more-info flag) using `messages.parse`.

COURSE CONCEPT (Building with the Claude API: structured outputs)
    `messages.parse` takes a Pydantic model and returns a validated instance - no
    prefill tricks, no "please output JSON" prompt begging. The SDK converts the
    Pydantic class to a JSON schema, the API constrains generation to that schema,
    and the SDK validates the result back into the class. In real work this is how you
    feed model output into code (tickets, databases, routers) without brittle parsing.
    This repo never uses assistant prefill to force a format; the schema does the job.

HOW TO RUN (from the repo root)
    export ANTHROPIC_API_KEY=...        # Windows PowerShell: $env:ANTHROPIC_API_KEY="..."
    python examples/api/03_structured_output.py
    Optional: CLAUDE_FAST_MODEL overrides the small model (see playbook.common.fast_model).

EXPECTED OUTPUT
    Pretty-printed JSON for the report, e.g. a short title, a severity such as "S2" (one
    of S1-S4), a component like the reports page, a list of reproduction steps, and a
    boolean `needs_more_info`. The exact wording varies run to run.

REPO MODULES USED
    playbook.common: fast_model() (cheap model - extraction is easy), get_client().

GOTCHAS / TRY NEXT
    * Keep the Pydantic model simple: field descriptions and Literal types become part
      of the schema the model sees, so they act as extra instructions. For the same
      reason there is deliberately no docstring on BugReport: a class docstring would
      also be sent as the schema description and change the request.
    * `parsed_output` can be None if the model refuses; production code should check
      `response.stop_reason` first.
    * Next: example 04 lets the model call your own functions.
"""
from typing import Literal

from pydantic import BaseModel, Field

from playbook.common import fast_model, get_client


# The target shape. Pydantic turns this class into the JSON schema sent to the API.
# (Comments, not a docstring: a docstring would become part of the schema.)
class BugReport(BaseModel):
    # Field(description=...) is passed to the model as guidance for this one field.
    title: str = Field(description="Under 10 words")
    # Literal restricts the value to exactly these four strings (an enum in the schema),
    # so downstream code can switch on severity without defensive parsing.
    severity: Literal["S1", "S2", "S3", "S4"]
    component: str
    steps_to_reproduce: list[str]
    # Lets the model say "this report is too vague" instead of inventing details.
    needs_more_info: bool


def extract_bug(client, raw_text: str) -> BugReport:
    """Turn free-form text into a validated BugReport.

    Args:
        client: an `anthropic.Anthropic` instance (injectable for tests).
        raw_text: the unstructured message, e.g. a chat or email from a user.

    Returns:
        A `BugReport` instance. Because the API enforces the schema, fields have the
        right types and `severity` is one of the allowed values.
    """
    response = client.messages.parse(
        # fast_model(): extraction into a small schema is easy, so use the cheaper,
        # lower-latency model. max_tokens=800 is ample for a short JSON object.
        # output_format: the Pydantic class describing the required output shape;
        # this is the structured-outputs feature (replaces prefill / "reply in JSON").
        model=fast_model(), max_tokens=800, output_format=BugReport,
        # The user text is wrapped in <message> tags so the model can tell the data
        # apart from the instruction (it also reduces prompt-injection risk).
        messages=[{"role": "user", "content": f"Turn this message into a bug report:\n<message>\n{raw_text}\n</message>"}],
    )
    # parsed_output is the already-validated BugReport (None if the output could not
    # be produced, for example on a refusal).
    return response.parsed_output


if __name__ == "__main__":
    text = ("hey, after the last deploy the export button on the reports page just spins forever "
            "for big date ranges. small ranges work. chrome on mac. blocks our month-end close!")
    print(extract_bug(get_client(), text).model_dump_json(indent=2))
