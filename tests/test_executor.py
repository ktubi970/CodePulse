from pathlib import Path

import pytest

from agent.executor import ExecutorError, WorkspaceExecutor, check_test_runtime
from agent.protocol import ReadFile, RunTests, WriteFile
from runner.manifests import load_manifest
from tests.test_manifests import write_task


def test_runtime_check_accepts_the_current_interpreter() -> None:
    assert "pytest" in check_test_runtime()


def test_runtime_check_fails_loudly_when_test_runner_is_missing() -> None:
    # Same failure mode as pytest living in user site-packages, which the runner disables.
    with pytest.raises(ExecutorError, match="cannot import"):
        check_test_runtime(module="codepulse_missing_test_runner")


def test_read_file_cannot_escape_editable_copy(tmp_path: Path) -> None:
    task = write_task(tmp_path)
    (task / "repo" / "safe.py").write_text("safe = True\n", encoding="utf-8")
    manifest = load_manifest(task)
    with WorkspaceExecutor.create(manifest, test_timeout_s=5) as executor:
        with pytest.raises(ExecutorError, match="escapes|outside"):
            executor.read_file("../verification/test_hidden.py")


def test_write_file_replaces_content_and_shows_in_final_diff(tmp_path: Path) -> None:
    task = write_task(tmp_path)
    (task / "repo" / "value.py").write_text("value = 1\n", encoding="utf-8")
    with WorkspaceExecutor.create(load_manifest(task), test_timeout_s=5) as executor:
        result = executor.execute(WriteFile(path="value.py", content="value = 2\n"))
        assert result.data["ok"] is True
        assert executor.read_file("value.py").data["content"] == "value = 2\n"
        executor.execute(WriteFile(path="pkg/new.py", content="x = 1\n"))
        diff = executor.final_diff()
    assert "+value = 2" in diff
    assert "+++ b/pkg/new.py" in diff


@pytest.mark.parametrize("path", ["../verification/test_hidden.py", "C:/outside.py", "/outside.py"])
def test_write_file_cannot_escape_editable_copy(tmp_path: Path, path: str) -> None:
    task = write_task(tmp_path)
    with WorkspaceExecutor.create(load_manifest(task), test_timeout_s=5) as executor:
        with pytest.raises(ExecutorError):
            executor.write_file(path, "pwned = True\n")
    assert not (task / "verification" / "test_hidden.py").exists()


def test_test_action_uses_manifest_vector_not_model_text(tmp_path: Path) -> None:
    task = write_task(tmp_path)
    tests = task / "repo" / "tests"
    tests.mkdir()
    (tests / "test_ok.py").write_text("def test_ok(): assert True\n", encoding="utf-8")
    manifest = load_manifest(task)
    with WorkspaceExecutor.create(manifest, test_timeout_s=5) as executor:
        result = executor.execute(RunTests())
    assert result.kind == "test_result"
    assert result.data["exit_code"] == 0
