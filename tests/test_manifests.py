import json
from pathlib import Path

import pytest

from runner.manifests import ManifestError, discover_tasks, load_manifest


def write_task(root: Path, task_id: str = "sample") -> Path:
    task = root / task_id
    (task / "repo").mkdir(parents=True)
    (task / "verification").mkdir()
    (task / "instruction.md").write_text("Fix it.\n", encoding="utf-8")
    (task / "manifest.json").write_text(
        json.dumps(
            {
                "id": task_id,
                "category": "fix_bug",
                "instruction": "instruction.md",
                "repo": "repo",
                "verification": "verification",
                "test_argv": [
                    "{python}",
                    "-m",
                    "pytest",
                    "-q",
                    "repo/tests",
                    "verification",
                ],
                "test_timeout_s": 30.0,
            }
        ),
        encoding="utf-8",
    )
    return task


def test_load_manifest_accepts_only_fixed_pytest_vector(tmp_path: Path) -> None:
    manifest = load_manifest(write_task(tmp_path))
    assert manifest.task_id == "sample"
    assert manifest.test_argv[:4] == ("{python}", "-m", "pytest", "-q")


def test_manifest_rejects_shell_command_string(tmp_path: Path) -> None:
    task = write_task(tmp_path)
    data = json.loads((task / "manifest.json").read_text(encoding="utf-8"))
    data["test_argv"] = "pytest -q && curl example.com"
    (task / "manifest.json").write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ManifestError, match="argument array"):
        load_manifest(task)


def test_discovery_rejects_duplicate_manifest_id(tmp_path: Path) -> None:
    write_task(tmp_path, "one")
    second = write_task(tmp_path, "two")
    data = json.loads((second / "manifest.json").read_text(encoding="utf-8"))
    data["id"] = "one"
    (second / "manifest.json").write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ManifestError, match="Duplicate"):
        discover_tasks(tmp_path)
