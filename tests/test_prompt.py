from agent.prompt import bounded_observation
from runner.config import BudgetConfig


def test_observation_fits_in_the_default_context_budget() -> None:
    text = "x" * 200_000
    bounded = bounded_observation(text)
    assert "OUTPUT TRUNCATED" in bounded
    # ~4 bytes per token: keep an observation well under the context window.
    assert len(bounded.encode("utf-8")) < BudgetConfig().context_tokens * 4 // 2 + 200


def test_small_observation_is_unchanged() -> None:
    assert bounded_observation('{"exit_code": 0}') == '{"exit_code": 0}'
