#!/usr/bin/env python3
"""Concept: retrieval-augmented generation - ground answers in YOUR documents.

WHAT IT SHOWS
    The repo's own docs/*.md files are split into chunks, the most relevant chunks for a
    question are found with a simple keyword-scoring search, and Claude answers using
    only those chunks, citing them as [1], [2], ...

COURSE CONCEPT (Building with the Claude API: retrieval-augmented generation)
    The model only knows its training data and what is in the prompt. RAG fixes that by
    retrieving the few passages that matter and putting them in the prompt, which keeps
    answers grounded and the prompt small (cheaper and more accurate than pasting a whole
    corpus). Pipeline: chunk -> retrieve (TF-IDF here; embeddings in production) -> prompt
    with numbered sources -> cited answer. The retrieval step is pure Python
    (playbook.rag) so it can be inspected and tested without the API.

HOW TO RUN (from the repo root - it reads the relative path `docs/`)
    export ANTHROPIC_API_KEY=...        # Windows PowerShell: $env:ANTHROPIC_API_KEY="..."
    python examples/api/11_rag_lite.py
    Only the final answer step calls the API; retrieval is local and free.

EXPECTED OUTPUT
    `Top chunks: [(index, score), ...]` - up to 3 chunk indexes with relevance scores,
    best first - then an answer naming the hooks feature of Claude Code with [n]
    citations, based on docs/claude-code-features.md.

REPO MODULES USED
    playbook.rag: chunk_text(), retrieve(), answer(). playbook.common: get_client().
    (rag.answer uses the default model via playbook.common.ask.)

GOTCHAS / TRY NEXT
    * Chunking is by words (size=120 words with 20 overlap) so a sentence is rarely cut
      off from its context. Tune size/overlap: too small loses context, too big wastes
      tokens and dilutes relevance.
    * TF-IDF only matches shared words; it misses synonyms. Embeddings fix that, and the
      rest of the pipeline stays unchanged.
    * Running from another directory finds no docs and produces an empty corpus.
    * Next: example 12 combines several calls into workflows.
"""
from pathlib import Path

from playbook import rag
from playbook.common import get_client

if __name__ == "__main__":
    # Read every markdown file under docs/ (sorted for deterministic chunk numbering)
    # and join them into one big string separated by blank lines.
    corpus = "\n\n".join(p.read_text(encoding="utf-8") for p in sorted(Path("docs").glob("*.md")))
    # size/overlap are measured in words: each chunk is 120 words and repeats the last
    # 20 words of the previous one so facts on a boundary are not lost.
    chunks = rag.chunk_text(corpus, size=120, overlap=20)
    question = "Which Claude Code feature runs scripts automatically before a tool call?"
    # Show which chunks were picked, as (chunk_index, score); useful to debug retrieval
    # quality separately from answer quality.
    print("Top chunks:", rag.retrieve(chunks, question))
    # answer() retrieves again, builds a prompt with numbered <source> tags, and asks the
    # model to answer only from them and cite as [id].
    print(rag.answer(get_client(), question, chunks))
