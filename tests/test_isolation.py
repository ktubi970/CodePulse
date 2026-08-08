from pathlib import Path

from agent.executor import WorkspaceExecutor
from runner.manifests import load_manifest
from tests.test_manifests import write_task


def test_original_repository_remains_unchanged(tmp_path: Path) -> None:
    task = write_task(tmp_path)
    source = task / "repo" / "value.py"
    source.write_text("value = 1\n", encoding="utf-8")
    manifest = load_manifest(task)
    with WorkspaceExecutor.create(manifest, test_timeout_s=5) as executor:
        assert executor.repo_root is not None
        executor.repo_root.joinpath("value.py").write_text("value = 2\n", encoding="utf-8")

    assert source.read_text(encoding="utf-8") == "value = 1\n"
