"""Shared helpers for the playbook examples.

``playbook`` is the importable package behind the runnable demos in ``examples/``
and the offline tests in ``tests/``.  Install it once with ``pip install -e .``
(the ``-e`` makes edits take effect immediately) and then ``import playbook.<module>``.

Modules, in rough dependency order:
  * ``common``    - model ids, client factory, one-shot ``ask`` helper (used by others)
  * ``sqlguard``  - read-only SQL validation / execution for SQLite
  * ``sampledb``  - builds a synthetic SQLite file with a planted data bug
  * ``tools``     - manual tool-use loop; uses ``sqlguard`` for its database tools
  * ``workflows`` - chain / route / parallelize / evaluator-optimizer patterns
  * ``evals``     - tiny prompt-evaluation harness
  * ``rag``       - retrieval-augmented generation with TF-IDF (no vector DB)

The package itself has no import-time side effects: this file only holds this docstring.
"""
