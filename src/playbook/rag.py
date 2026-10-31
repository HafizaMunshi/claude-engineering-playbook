"""Retrieval-augmented generation without any vector DB.

WHAT: a complete miniature RAG pipeline: split documents into chunks, find the chunks
most relevant to a question, put them in the prompt as numbered sources, and ask the
model to answer with [n] citations.

WHY: RAG lets a model answer from YOUR documents (which it was not trained on) and
lets you check its claims against the cited sources.  Seeing it without a vector
database shows the idea is simple; embeddings are an upgrade to step 2, not the point.

Chunk -> score with TF-IDF -> stuff the top-k into the prompt as numbered sources
-> ask for answers with [n] citations. Swap ``retrieve`` for embeddings later;
the rest of the pipeline stays identical.

What is TF-IDF?  "Term Frequency x Inverse Document Frequency".  A word scores high for
a chunk if it appears OFTEN in that chunk (TF) but in FEW chunks overall (IDF) - so
rare, distinctive words like "invoice" count for more than "the".  It is keyword
matching with smart weights: it will NOT match synonyms ("car" vs "automobile"), which
is the main thing embeddings improve.

HOW IT FITS: ``answer`` calls ``common.ask`` for the model step.  Demo:
``examples/api/11_*``; tests: ``tests/test_evals_and_rag.py`` (retrieval is pure Python,
so it is tested offline).

Limitations: scoring is recomputed over all chunks on every query (fine for demos,
slow for large corpora); the tokenizer only understands ASCII letters and digits.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any

from playbook.common import ask

# One token = a run of lowercase ASCII letters/digits.  Everything else (spaces,
# punctuation, accented letters, non-Latin scripts) acts as a separator.
_TOKEN = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    """Lower-case ``text`` and split it into word tokens (see ``_TOKEN``)."""
    return _TOKEN.findall(text.lower())


def chunk_text(text: str, size: int = 400, overlap: int = 60) -> list[str]:
    """Word-based sliding window so a sentence is rarely split from its context.

    Why chunk?  Only the few relevant passages should go into the prompt (cheaper,
    less distraction).  Why overlap?  Consecutive chunks share ``overlap`` words, so a
    sentence cut at one boundary still appears whole in the neighbouring chunk.

    Args:
        size: words per chunk.
        overlap: words shared with the previous chunk; the window advances by
            ``size - overlap`` (at least 1, so a bad setting cannot loop forever).
    Returns:
        List of chunk strings; ``[]`` for empty input.  Note the final chunk(s) may be
        short and largely repeat the end of the previous chunk.
    """
    words = text.split()
    step = max(size - overlap, 1)
    # ``max(len(words), 1)`` keeps range() valid for empty text; the trailing
    # ``if words[i:i + size]`` filter then drops empty slices.
    return [" ".join(words[i:i + size]) for i in range(0, max(len(words), 1), step) if words[i:i + size]]


def retrieve(chunks: list[str], query: str, k: int = 3) -> list[tuple[int, float]]:
    """Return [(chunk_index, score)] best-first using TF-IDF cosine-like scoring.

    Steps:
      1. ``docs``: a term->count table (Counter) per chunk.
      2. ``df`` (document frequency): in how many chunks does each term appear?
      3. ``idf``: ``log((n+1)/(df+1)) + 1`` - rarer terms get larger weights.  The
         ``+1`` terms ("smoothing") avoid division by zero and keep weights positive.
      4. Per chunk: ``dot`` = sum over query terms present in the chunk of
         ``query_count * chunk_count * idf**2`` (idf appears squared because it
         weights both the query side and the document side).
      5. Divide by the chunk's vector length (``norm``) so long chunks do not win just
         for containing more words.  ``or 1.0`` guards an empty chunk.
      6. Drop zero scores (no shared words), sort best-first, keep the top ``k``.

    Returns:
        ``[]`` if nothing matches.  Scores are only comparable within one call.
    """
    docs = [Counter(tokenize(c)) for c in chunks]
    n = len(docs)
    df = Counter(term for d in docs for term in d)
    idf = {t: math.log((n + 1) / (c + 1)) + 1 for t, c in df.items()}
    q = Counter(tokenize(query))
    scores = []
    for i, d in enumerate(docs):
        dot = sum(q[t] * d[t] * idf.get(t, 0) ** 2 for t in q if t in d)
        norm = math.sqrt(sum((v * idf[t]) ** 2 for t, v in d.items())) or 1.0
        scores.append((i, dot / norm))
    return sorted((s for s in scores if s[1] > 0), key=lambda s: s[1], reverse=True)[:k]


def build_prompt(question: str, sources: list[str]) -> str:
    """Assemble the final prompt: instructions, numbered sources, then the question.

    Sources are numbered from 1 and wrapped in ``<source id="n">`` tags so the model can
    cite them as ``[n]``.  The instruction "ONLY the sources ... say you don't know"
    discourages the model from inventing answers when retrieval found nothing useful.
    Note the source text is inserted unescaped: a malicious document could contain
    instructions (prompt injection), so only index content you trust.
    """
    numbered = "\n".join(f'<source id="{i + 1}">{s}</source>' for i, s in enumerate(sources))
    return (f"Answer using ONLY the sources. Cite as [id]. If the answer is not in the sources, "
            f"say you don't know.\n\n{numbered}\n\nQuestion: {question}")


def answer(client: Any, question: str, chunks: list[str], k: int = 3) -> str:
    """End-to-end RAG: retrieve the top ``k`` chunks, build the prompt, ask the model.

    Returns the model's text.  If retrieval finds nothing, the prompt contains no
    sources and the model is told to say it does not know.
    """
    hits = retrieve(chunks, question, k)
    sources = [chunks[i] for i, _ in hits]
    return ask(client, build_prompt(question, sources), max_tokens=800)
