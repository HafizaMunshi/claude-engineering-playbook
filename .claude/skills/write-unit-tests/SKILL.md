---
name: write-unit-tests
description: Use when asked to add or improve unit tests for existing code, or to cover a bug fix with a regression test. Works test-first for bugs and behaviour-first for existing code.
---

# Write unit tests

## Procedure
1. Read the unit under test and the nearest existing test file; match their framework, fixtures and naming.
2. List behaviours, not methods: happy path, boundaries (empty, one, many, max), invalid input, error propagation, and any state/ordering rule.
3. For a **bug fix**: write the failing test first, run it, confirm it fails for the right reason, then fix.
4. Write one assertion-focused test per behaviour, named `test_<unit>_<condition>_<expected>`.
5. Mock only true boundaries (network, clock, filesystem, DB). Do not mock the unit's own collaborators if a real one is cheap.
6. Run the test file, then the whole suite. Report the command and the result.

## Quality bar
- A test must fail if the behaviour breaks. Mutate the code mentally: would this test notice?
- No sleeps, no order dependence, no reliance on real time or network.
- Prefer parametrised tests over copy-pasted bodies.

## Do not
- Chase 100% coverage with assertion-free tests.
- Change production code to make tests easier unless asked; suggest it instead.
