from collections import deque
from pathlib import Path

from agent.loop import run_agent
from agent.ollama import OllamaModel, OllamaReply
from runner.config import BudgetConfig
from runner.manifests import load_manifest
from runner.storage import ResultStore
from tests.test_manifests import write_task


class ScriptedClient:
    def __init__(self, replies: list[str]) -> None:
        self.replies = deque(replies)

    def chat(self, **kwargs: object) -> OllamaReply:
        content = self.replies.popleft() if self.replies else '{"action":"finish","summary":"done"}'
        return OllamaReply(
            content=content,
            prompt_tokens=10,
            completion_tokens=5,
            total_duration_ns=1_000_000,
        )


def test_agent_success_requires_fresh_final_test(tmp_path: Path) -> None:
    task = write_task(tmp_path)
    (task / "repo" / "value.py").write_text("value = 1\n", encoding="utf-8")
    tests = task / "repo" / "tests"
    tests.mkdir(exist_ok=True)
    (tests / "test_value.py").write_text(
        "from value import value\n\ndef test_value(): assert value == 2\n",
        encoding="utf-8",
    )
    client = ScriptedClient(
        [
            '{"action":"apply_patch","patch":"--- a/value.py\\n+++ b/value.py\\n@@ -1 +1 @@\\n-value = 1\\n+value = 2\\n"}',
            '{"action":"finish","summary":"fixed"}',
        ]
    )
    store = ResultStore(tmp_path / "runs.sqlite3")

    outcome = run_agent(
        client=client,
        model=OllamaModel("local:test", "abc", "1B", "Q4"),
        ollama_version="0.test",
        manifest=load_manifest(task),
        budget=BudgetConfig(),
        store=store,
    )

    assert outcome.success is True
    assert outcome.final_test.exit_code == 0
    assert outcome.test_runs == 1


def test_agent_can_solve_task_with_write_file(tmp_path: Path) -> None:
    task = write_task(tmp_path)
    (task / "repo" / "value.py").write_text("value = 1\n", encoding="utf-8")
    tests = task / "repo" / "tests"
    tests.mkdir(exist_ok=True)
    (tests / "test_value.py").write_text(
        "from value import value\n\ndef test_value(): assert value == 2\n",
        encoding="utf-8",
    )
    client = ScriptedClient(
        [
            '{"action":"write_file","path":"value.py","content":"value = 2\\n","summary":"fix"}',
            '{"action":"finish"}',
        ]
    )

    outcome = run_agent(
        client=client,
        model=OllamaModel("local:test", "abc", "1B", "Q4"),
        ollama_version="0.test",
        manifest=load_manifest(task),
        budget=BudgetConfig(),
        store=ResultStore(tmp_path / "runs.sqlite3"),
    )

    assert outcome.success is True
    assert "+value = 2" in outcome.final_patch


def test_immediate_finish_fails_if_tests_fail(tmp_path: Path) -> None:
    task = write_task(tmp_path)
    tests = task / "repo" / "tests"
    tests.mkdir(exist_ok=True)
    (tests / "test_fail.py").write_text("def test_fail(): assert False\n", encoding="utf-8")
    client = ScriptedClient(['{"action":"finish","summary":"done"}'])
    store = ResultStore(tmp_path / "runs.sqlite3")

    outcome = run_agent(
        client=client,
        model=OllamaModel("local:test", "abc", "1B", "Q4"),
        ollama_version="0.test",
        manifest=load_manifest(task),
        budget=BudgetConfig(),
        store=store,
    )

    assert outcome.success is False
    assert outcome.status == "tests_failed"
