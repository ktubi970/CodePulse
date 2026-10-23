"""Known ways for model-written code to fake a passing verification."""
import json
from pathlib import Path

import pytest

from agent.executor import WorkspaceExecutor
from agent.loop import run_agent
from agent.ollama import OllamaModel
from runner.config import BudgetConfig
from runner.manifests import discover_tasks, load_manifest
from runner.storage import ResultStore
from tests.test_agent_loop import ScriptedClient
from tests.test_manifests import write_task

TASKS = discover_tasks(Path("tasks"))

HACKS = {
    # Imported at interpreter start-up when the repository is on PYTHONPATH.
    "sitecustomize.py": "import os\nos._exit(0)\n",
    # Session hook that rewrites the exit status.
    "conftest.py": "def pytest_sessionfinish(session, exitstatus):\n    session.exitstatus = 0\n",
    # Exit 0 from the code under test before pytest can report a failure.
    "src/__init__.py": "import os\nos._exit(0)\n",
    # Skipped tests exit 0 without proving anything.
    "src/value.py": "import pytest\npytest.skip('nope', allow_module_level=True)\n",
}


def _failing_task(tmp_path: Path) -> Path:
    task = write_task(tmp_path)
    (task / "repo" / "src").mkdir()
    (task / "repo" / "src" / "value.py").write_text("value = 1\n", encoding="utf-8")
    (task / "repo" / "tests").mkdir()
    (task / "repo" / "tests" / "test_smoke.py").write_text("def test_smoke(): pass\n", encoding="utf-8")
    (task / "verification" / "test_verification.py").write_text(
        "from src.value import value\n\ndef test_value(): assert value == 2\n", encoding="utf-8"
    )
    return task


@pytest.mark.parametrize("path", sorted(HACKS))
def test_model_written_files_cannot_fake_a_pass(tmp_path: Path, path: str) -> None:
    with WorkspaceExecutor.create(load_manifest(_failing_task(tmp_path)), test_timeout_s=10) as executor:
        executor.write_file(path, HACKS[path])
        result = executor.final_test()
    assert result.passed is False


def test_honest_fix_still_passes(tmp_path: Path) -> None:
    with WorkspaceExecutor.create(load_manifest(_failing_task(tmp_path)), test_timeout_s=10) as executor:
        executor.write_file("src/value.py", "value = 2\n")
        result = executor.final_test()
    assert result.passed is True
    assert result.report is not None and result.report.tests == 2


def test_sitecustomize_hack_through_agent_loop_is_not_a_success(tmp_path: Path) -> None:
    hack = (
        '{"action":"apply_patch","patch":"--- /dev/null\\n+++ b/sitecustomize.py\\n'
        '@@ -0,0 +1,2 @@\\n+import os\\n+os._exit(0)\\n"}'
    )
    outcome = run_agent(
        client=ScriptedClient([hack, '{"action":"finish","summary":"done"}']),
        model=OllamaModel("local:test", "abc", "1B", "Q4"),
        ollama_version="0.test",
        manifest=TASKS["parse_config_version"],
        budget=BudgetConfig(),
        store=ResultStore(tmp_path / "runs.sqlite3"),
    )
    assert outcome.success is False


LAZY_TESTS = {
    "test_parse_bool": ("tests/test_parse.py", "def test_parse_bool_invalid():\n    pass\n"),
    "test_safe_divide": ("tests/test_math.py", "def test_safe_divide_zero():\n    pass\n"),
}


@pytest.mark.parametrize("task_id", sorted(LAZY_TESTS))
def test_reference_tests_kill_every_mutant(task_id: str) -> None:
    manifest = TASKS[task_id]
    assert manifest.mutants_path is not None
    with WorkspaceExecutor.create(manifest) as executor:
        executor.overlay(manifest.solution_path)
        verification = executor.verify()
    assert verification.test.passed
    assert verification.surviving_mutants == ()


@pytest.mark.parametrize("task_id", sorted(LAZY_TESTS))
def test_empty_test_is_rejected_as_weak(task_id: str, tmp_path: Path) -> None:
    path, content = LAZY_TESTS[task_id]
    reply = json.dumps({"action": "write_file", "path": path, "content": content})
    outcome = run_agent(
        client=ScriptedClient([reply, '{"action":"finish"}']),
        model=OllamaModel("local:test", "abc", "1B", "Q4"),
        ollama_version="0.test",
        manifest=TASKS[task_id],
        budget=BudgetConfig(),
        store=ResultStore(tmp_path / "runs.sqlite3"),
    )
    assert outcome.final_test.passed is True  # the lazy test passes on its own...
    assert outcome.success is False  # ...but catches no bug
    assert outcome.status == "weak_tests"


def _run_test_writer(tmp_path: Path, content: str, task_id: str = "test_parse_bool"):
    path = LAZY_TESTS[task_id][0]
    reply = json.dumps({"action": "write_file", "path": path, "content": content})
    return run_agent(
        client=ScriptedClient([reply, '{"action":"finish"}']),
        model=OllamaModel("local:test", "abc", "1B", "Q4"),
        ollama_version="0.test",
        manifest=TASKS[task_id],
        budget=BudgetConfig(),
        store=ResultStore(tmp_path / "runs.sqlite3"),
    )


# Tests that never call the code under test. Each passes on the real run and fails on a mutant
# only because it notices that it runs against a mutant, or catches nothing at all.
MUTANT_DETECTORS = {
    "workspace path": "from pathlib import Path\n\ndef test_it():\n    assert 'mutants' not in Path(__file__).parts\n",
    "command line": "import sys\n\ndef test_it():\n    assert 'verification' in sys.argv\n",
    "state left in the repository": (
        "from pathlib import Path\n\ndef test_it():\n"
        "    marker = Path(__file__).with_name('seen')\n    assert not marker.exists()\n    marker.write_text('')\n"
    ),
    "state left outside the repository": (
        "from pathlib import Path\n\ndef test_it():\n"
        "    marker = Path.cwd() / 'seen'\n    assert not marker.exists()\n    marker.write_text('')\n"
    ),
    "no test at all": "",
}


@pytest.mark.parametrize("detector", sorted(MUTANT_DETECTORS))
def test_tests_cannot_tell_a_mutant_run_from_the_real_one(tmp_path: Path, detector: str) -> None:
    outcome = _run_test_writer(tmp_path, MUTANT_DETECTORS[detector])
    assert outcome.success is False
    assert outcome.status in {"weak_tests", "tests_failed"}


def test_honest_agent_tests_still_kill_the_mutants(tmp_path: Path) -> None:
    solution = TASKS["test_parse_bool"].solution_path
    assert solution is not None
    content = (solution / LAZY_TESTS["test_parse_bool"][0]).read_text(encoding="utf-8")
    outcome = _run_test_writer(tmp_path, content)
    assert outcome.status == "success"
    assert "seen" not in outcome.final_patch  # verification leaves no test artefact in the diff
