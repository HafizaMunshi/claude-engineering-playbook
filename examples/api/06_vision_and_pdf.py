#!/usr/bin/env python3
"""Concept: multimodal input - images and PDFs as content blocks (base64).

WHAT IT SHOWS
    A user message whose `content` is a LIST of blocks: first an `image` or `document`
    block holding a base64-encoded file, then a `text` block with the question. Claude
    answers about the file (explain a diagram, extract requirements from a spec PDF).

COURSE CONCEPT (Building with the Claude API: vision and PDF support)
    So far `content` was a plain string. A string is shorthand for one text block; to send
    anything else you pass a list of typed blocks:
      * "text"     - ordinary prose;
      * "image"    - png/jpeg/gif/webp, sent as base64 (or a URL);
      * "document" - a PDF (the API reads both its text and its page images).
    Real-world uses: architecture diagrams, screenshots of bugs, scanned invoices, specs.
    Cost note: images and PDF pages are converted to input tokens, so big files cost
    real money on every call (cache them if you ask many questions, see example 07).

HOW TO RUN: this script exits with this very docstring as usage text when called with
the wrong number of arguments, so keep the two usage lines below accurate. Needs
ANTHROPIC_API_KEY set in the environment.

    python examples/api/06_vision_and_pdf.py diagram.png "Explain this architecture diagram"
    python examples/api/06_vision_and_pdf.py spec.pdf "List the requirements as a checklist"
"""
import base64
import mimetypes
import sys
from pathlib import Path

from playbook.common import get_client, model, text_of


def file_block(path: str) -> dict:
    """Build the right content block for an image or PDF.

    Args:
        path: path of a local file. The type is guessed from the file extension.

    Returns:
        A content-block dict: `document` for PDFs, `image` for image/* types.

    Raises:
        ValueError: if the extension is neither a PDF nor an image type.
    """
    # The API takes binary files as base64 text. standard_b64encode returns bytes;
    # decode("ascii") makes it a str that can live inside the JSON request body.
    data = base64.standard_b64encode(Path(path).read_bytes()).decode("ascii")
    # Guess the MIME type from the filename (e.g. "image/png"); "" if unknown.
    mime = mimetypes.guess_type(path)[0] or ""
    if mime == "application/pdf":
        # "document" block: used for PDFs. source.type "base64" means the bytes are inline.
        return {"type": "document", "source": {"type": "base64", "media_type": mime, "data": data}}
    if mime.startswith("image/"):
        # "image" block: media_type must match the real format or the API rejects it.
        return {"type": "image", "source": {"type": "base64", "media_type": mime, "data": data}}
    raise ValueError(f"unsupported file type: {path}")


def describe(client, path: str, question: str) -> str:
    """Ask a question about one local image or PDF.

    Args:
        client: an `anthropic.Anthropic` instance (injectable for tests).
        path: file to attach (see `file_block`).
        question: what to ask about the file.

    Returns:
        The model's answer as plain text.
    """
    # Order matters for quality: put the media first and the question after it, so the
    # model reads the file before it knows what it is being asked.
    content = [file_block(path), {"type": "text", "text": question}]  # media first, question last
    # max_tokens=2000 leaves room for a detailed explanation or a long checklist.
    response = client.messages.create(model=model(), max_tokens=2000,
                                      messages=[{"role": "user", "content": content}])
    return text_of(response)


if __name__ == "__main__":
    # Exactly two arguments are required (file and question). Raising SystemExit with a
    # string prints it to stderr and exits non-zero - here that string is the docstring.
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    print(describe(get_client(), sys.argv[1], sys.argv[2]))
