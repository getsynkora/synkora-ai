"""
Eval regression test suite.

Runs golden test cases from tests/eval/datasets/*.yaml against the LLM judge.
Results are pushed to Langfuse when LANGFUSE_* env vars are set.

Run:
    pytest -m eval -v
    pytest -m eval -v --tb=short -k "factual"  # filter by tag
"""

import pytest

from tests.eval.conftest import load_all_cases, push_results_to_langfuse

_ALL_CASES = load_all_cases()
_results_collected: list[dict] = []


@pytest.fixture(autouse=True, scope="session")
def _push_langfuse_at_end():
    """After all eval tests finish, push results to Langfuse."""
    yield
    if _results_collected:
        push_results_to_langfuse(_results_collected)


@pytest.mark.eval
@pytest.mark.asyncio
@pytest.mark.parametrize("case", _ALL_CASES, ids=[f"{c['dataset']}/{c['input'][:30]}" for c in _ALL_CASES])
async def test_eval_case(judge, case):
    """
    For each golden test case: run it through the judge and assert it passes.

    The judge uses the configured eval_judge_model (default: gpt-4o-mini) to evaluate
    whether the actual output meets the expected criteria. A score >= 0.7 = passed.

    NOTE: These tests require a configured LLM provider (OPENAI_API_KEY or equivalent).
    They are excluded from the standard test run and only run with -m eval.
    """
    # For regression tests we evaluate the judge itself on well-known answers
    # In a full integration test, actual would come from agent.chat(case["input"])
    # For the regression suite the "actual" is the criteria itself (sanity check)
    actual = case["criteria"]  # Replace with agent.chat(case["input"]) for full e2e

    result = await judge.score(case["input"], case["criteria"], actual)

    _results_collected.append(
        {
            "dataset": case["dataset"],
            "input": case["input"],
            "criteria": case["criteria"],
            "actual": actual,
            "score": result.score,
            "passed": result.passed,
            "reasoning": result.reasoning,
        }
    )

    assert result.passed, (
        f"Eval failed for: {case['input']!r}\n"
        f"Criteria: {case['criteria']}\n"
        f"Score: {result.score:.2f}\n"
        f"Reasoning: {result.reasoning}"
    )
