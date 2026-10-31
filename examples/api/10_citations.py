#!/usr/bin/env python3
"""Concept: citations - answers that point at the exact passage of a source document.

WHAT IT SHOWS
    A short rollback-policy runbook is attached as a `document` block with citations
    enabled. The reply comes back as several text blocks; each one that relies on the
    runbook carries the exact quoted passage it was based on.

COURSE CONCEPT (Building with the Claude API: citations)
    Instead of asking the model to "quote your sources" in prose (which it can get wrong),
    you turn on `citations` per document block. The API then returns structured citation
    objects attached to the text blocks, pointing at the real span of the source. Great
    for policy/runbook Q&A, legal or support answers, anywhere a human must verify the
    claim. Compare with example 11, which does retrieval and "[id]" citations by prompting.

HOW TO RUN (from the repo root)
    export ANTHROPIC_API_KEY=...        # Windows PowerShell: $env:ANTHROPIC_API_KEY="..."
    python examples/api/10_citations.py

EXPECTED OUTPUT
    The answer text in pieces, each piece followed by lines like `   [cited] "<quote>"`.
    Pieces without a citation (connective text) print with no quotes. For example, the
    5xx-over-2% rule and the "migrations are never rolled back automatically" rule should
    appear as cited quotes from the runbook.

REPO MODULES USED
    playbook.common: get_client(), model().

GOTCHAS / TRY NEXT
    * Citations are positional: `block.citations` is None (or empty) for text that is not
      based on the document, hence the `or []` guard.
    * `cited_text` is the quoted span; plain-text sources also carry character offsets
      (PDFs carry page numbers) if you need to highlight the source in a UI.
    * The cited text does not count toward output tokens, but the document itself is
      input tokens - cache it (example 07) if you ask many questions of the same document.
    * Next: example 11 builds retrieval from scratch.
"""
from playbook.common import get_client, model

RUNBOOK = """Rollback policy. Any deploy that raises the 5xx rate above 2% for five minutes must be rolled back.
Rollbacks are performed by the on-call engineer. Database migrations are never rolled back automatically;
they require a forward-fix migration reviewed by a second engineer."""


def ask_document(client, document_text: str, question: str) -> list[tuple[str, list[str]]]:
    """Ask a question about a text document and return each answer piece with its quotes.

    Args:
        client: an `anthropic.Anthropic` instance (injectable for tests).
        document_text: plain text of the source document.
        question: what to ask about the document.

    Returns:
        A list of (text, quotes) pairs, one per text block in the reply, where `quotes`
        is the list of source passages cited by that block (possibly empty).
    """
    response = client.messages.create(
        model=model(), max_tokens=800,
        messages=[{"role": "user", "content": [
            # "document" block: a source the model can read and cite.
            # title: a label for the document (shown to the model, useful with many docs).
            # citations {"enabled": True}: ask the API to attach citations to the answer.
            # source: where the content comes from. type "text" = plain text given inline,
            #   with media_type "text/plain" and the content in `data`.
            {"type": "document", "title": "Runbook", "citations": {"enabled": True},
             "source": {"type": "text", "media_type": "text/plain", "data": document_text}},
            # The question goes after the document, as a normal text block.
            {"type": "text", "text": question},
        ]}],
    )
    result = []
    # The reply is split into multiple text blocks so citations can attach to the exact
    # sentence they support, instead of to one big blob.
    for block in response.content:
        if block.type == "text":
            # Each citation has `cited_text`, the verbatim span from the document.
            quotes = [c.cited_text for c in (block.citations or [])]
            result.append((block.text, quotes))
    return result


if __name__ == "__main__":
    for text, quotes in ask_document(get_client(), RUNBOOK, "When must we roll back, and can migrations be rolled back?"):
        print(text, *[f'\n   [cited] "{q}"' for q in quotes])
