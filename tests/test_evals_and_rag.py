"""Tests for playbook.evals (prompt-evaluation harness) and playbook.rag (retrieval).

evals: a dataset of Case objects is graded automatically so prompt changes are judged by
pass-rate, not by eyeballing one output. rag: a dependency-free TF-IDF retriever plus
chunking and prompt building, so the whole retrieval pipeline is testable offline.

Run: .venv\\Scripts\\python.exe -m pytest tests/test_evals_and_rag.py -q
"""
from playbook import rag
from playbook.evals import Case, Verdict, compare, grade, run_eval


def test_graders():
    """The three deterministic graders: exact (trimmed, case-insensitive), contains, regex.

    Plus a negative case ("medium" is not "high"). A grader that is too lenient makes bad
    prompts look good; too strict makes good prompts look bad.
    """
    assert grade(Case("q", "High", "exact"), " high ")
    assert grade(Case("q", "timeout", "contains"), "Request TIMEOUT occurred")
    assert grade(Case("q", r"^\d{3}$", "regex"), "404")
    assert not grade(Case("q", "high", "exact"), "medium")


def test_model_grader_uses_schema_verdict(fake):
    """LLM-as-judge: the "model" grader returns the judge's structured `correct` flag.

    The fake scripts the judge's Verdict, so this checks only the plumbing (parse call ->
    .correct), with no network. Fails if the verdict field is read wrongly.
    """
    client = fake(parse=[Verdict(correct=True, reason="same meaning")])
    assert grade(Case("q", "reference", "model"), "paraphrase", client)


def test_run_eval_reports_failures_and_pass_rate():
    """2 of 3 cases pass; the report lists the failing case and compare() shows 67%.

    The system under test is a plain lambda (no model). Protects the numbers people use to
    compare prompt versions, and that failures carry enough detail to debug.
    """
    cases = [Case("a", "x"), Case("b", "y"), Case("c", "z")]
    report = run_eval(lambda text: {"a": "x", "b": "y"}.get(text, "wrong"), cases)
    assert (report["passed"], report["total"]) == (2, 3)
    assert report["failures"][0]["input"] == "c"
    assert "67%" in compare({"v1": report})


def test_retrieval_ranks_the_relevant_chunk_first():
    """The chunk about hooks (index 0) outranks unrelated chunks for a hooks question.

    Guards the TF-IDF scoring; if ranking breaks, RAG stuffs irrelevant sources into the
    prompt and answers degrade silently.
    """
    chunks = ["Hooks run scripts before a tool call and can block it.",
              "Skills are folders with a SKILL.md file.",
              "Batches are cheaper for bulk work."]
    ranked = rag.retrieve(chunks, "which feature blocks a tool call with a script", k=2)
    assert ranked[0][0] == 0


def test_retrieval_returns_nothing_when_no_overlap():
    """No shared terms -> empty result, not a random chunk.

    Lets the caller say "I don't know" instead of answering from irrelevant text.
    """
    assert rag.retrieve(["alpha beta"], "gamma") == []


def test_chunking_overlaps_and_covers_text():
    """Sliding-window chunks overlap by `overlap` words and the last chunk reaches the end.

    100 words, size 40, overlap 10 -> step 30. The overlap keeps sentences from being cut off
    from their context; "w99" in the last chunk proves no tail text is dropped.
    """
    text = " ".join(f"w{i}" for i in range(100))
    chunks = rag.chunk_text(text, size=40, overlap=10)
    assert chunks[0].split()[-10:] == chunks[1].split()[:10]
    assert "w99" in chunks[-1]


def test_prompt_numbers_sources_and_demands_citations():
    """Sources are numbered from 1 in <source id> tags and the prompt requires [id] citations.

    Citations only work if ids in the prompt match what the model is told to cite; this
    pins the exact format and the citation instruction.
    """
    prompt = rag.build_prompt("why?", ["first", "second"])
    assert '<source id="2">second</source>' in prompt and "Cite as [id]" in prompt
