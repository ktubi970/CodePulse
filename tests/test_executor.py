from pathlib import Path

import pytest

from agent.executor import ExecutorError, WorkspaceExecutor
from agent.protocol import ReadFile, RunTests
from runner.manifests import load_manifest
from tests.test_manifests import write_task


def test_read_file_cannot_escape_editable_copy(tmp_path: Path) -> None:
    task = write_task(tmp_path)
    (task / "repo" / "safe.py").write_text("safe = True\n", encoding="utf-8")
    manifest = load_manifest(task)
    with WorkspaceExecutor.create(manifest, test_timeout_s=5) as executor:
        with pytest.raises(ExecutorError, match="escapes|outside"):
            executor.read_file("../verification/test_hidden.py")


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
