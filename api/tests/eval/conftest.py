"""
Eval test fixtures and helpers.

Usage:
    pytest -m eval                         # run all eval cases
    LANGFUSE_PUBLIC_KEY=... pytest -m eval  # run + push results to Langfuse
"""

import os
from pathlib import Path

import pytest
import yaml


def load_all_cases() -> list[dict]:
    """Load all YAML datasets from tests/eval/datasets/ and return flat list of cases."""
    datasets_dir = Path(__file__).parent / "datasets"
    cases: list[dict] = []
    for yaml_file in sorted(datasets_dir.glob("*.yaml")):
        with open(yaml_file) as f:
            data = yaml.safe_load(f)
        dataset_name = data.get("dataset", yaml_file.stem)
        for case in data.get("cases", []):
            cases.append(
                {
                    "dataset": dataset_name,
                    "input": case["input"],
                    "criteria": case["criteria"],
                    "tags": case.get("tags", []),
                }
            )
    return cases


class JudgeHelper:
    """LLM-as-judge helper for eval tests."""

    def __init__(self):
        from src.config.settings import settings

        self.model = settings.eval_judge_model
        self.max_tokens = settings.eval_judge_max_tokens

    async def score(self, input_text: str, criteria: str, actual: str) -> "JudgeResult":
        from src.services.eval.judge_service import _call_judge

        llm_config = await self._load_llm_config()
        result = await _call_judge(input_text, criteria, actual, llm_config)
        return JudgeResult(**result)

    async def _load_llm_config(self):
        """Load ModelConfig from DB using EVAL_JUDGE_LLM_CONFIG_ID setting."""
        from src.config.settings import settings
        from src.services.agents.config import ModelConfig

        config_id = settings.eval_judge_llm_config_id
        if not config_id:
            pytest.skip("EVAL_JUDGE_LLM_CONFIG_ID not set — no LLM config available for judge")

        from uuid import UUID

        from sqlalchemy import select

        from src.core.database import get_async_session_factory
        from src.models.agent_llm_config import AgentLLMConfig
        from src.services.agents.llm_config_service import LLMConfigService

        session_factory = get_async_session_factory()
        async with session_factory() as db:
            result = await db.execute(select(AgentLLMConfig).filter(AgentLLMConfig.id == UUID(config_id)))
            row = result.scalar_one_or_none()

        if not row:
            pytest.skip(f"AgentLLMConfig {config_id} not found in DB")

        api_key = LLMConfigService.get_decrypted_api_key(row)
        return ModelConfig(
            provider=row.provider,
            model_name=self.model or row.model_name,
            max_tokens=self.max_tokens,
            api_key=api_key,
            api_base=row.api_base,
        )


class JudgeResult:
    def __init__(self, score: float, passed: bool, reasoning: str):
        self.score = score
        self.passed = passed
        self.reasoning = reasoning


@pytest.fixture(scope="session")
def judge():
    return JudgeHelper()


def push_results_to_langfuse(results: list[dict]) -> None:
    """Push eval results to Langfuse as a dataset run (called at session end if configured)."""
    required = ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY", "LANGFUSE_HOST")
    if not all(os.getenv(k) for k in required):
        return
    try:
        from langfuse import Langfuse

        client = Langfuse(
            public_key=os.environ["LANGFUSE_PUBLIC_KEY"],
            secret_key=os.environ["LANGFUSE_SECRET_KEY"],
            host=os.environ["LANGFUSE_HOST"],
        )
        run_name = f"pytest-eval-{os.getenv('CI_COMMIT_SHA', 'local')[:8]}"
        dataset_name = "pytest-regression"
        try:
            client.create_dataset(name=dataset_name)
        except Exception:
            pass

        for r in results:
            try:
                item = client.create_dataset_item(
                    dataset_name=dataset_name,
                    input=r["input"],
                    expected_output=r["criteria"],
                )
                client.trace(
                    name=run_name,
                    input=r["input"],
                    output=r["actual"],
                    metadata={"score": r["score"], "passed": r["passed"], "dataset": r["dataset"]},
                )
                item.link(run_name, r["actual"])
            except Exception:
                pass

        client.flush()
    except Exception as e:
        print(f"Langfuse push failed (non-critical): {e}")
