from pathlib import Path

import pytest

from agent.patches import PatchError, apply_patch, build_final_diff, snapshot_tree
from agent.protocol import ProtocolError, relative_path


def test_apply_patch_changes_only_declared_relative_file(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("value = 1\n", encoding="utf-8")
    changed = apply_patch(
        tmp_path,
        "--- a/a.py\n+++ b/a.py\n@@ -1 +1 @@\n-value = 1\n+value = 2\n",
        check_path=relative_path,
    )
    assert changed == ("a.py",)
    assert (tmp_path / "a.py").read_text(encoding="utf-8") == "value = 2\n"


def test_apply_patch_checks_every_path_git_would_touch(tmp_path: Path) -> None:
    (tmp_path / "old.py").write_text("old = 1\n", encoding="utf-8")
    checked: list[str] = []
    patch = (
        "--- /dev/null\n+++ b/new.py\n@@ -0,0 +1 @@\n+new = 1\n"
        "--- a/old.py\n+++ /dev/null\n@@ -1 +0,0 @@\n-old = 1\n"
    )
    apply_patch(tmp_path, patch, check_path=checked.append)
    assert sorted(checked) == ["new.py", "old.py"]


@pytest.mark.parametrize("target", ["../outside.py", "C:/secret.py", "src/a.py:stream"])
def test_apply_patch_stops_at_the_path_check(tmp_path: Path, target: str) -> None:
    with pytest.raises(ProtocolError):
        apply_patch(tmp_path, f"--- /dev/null\n+++ b/{target}\n@@ -0,0 +1 @@\n+x = 1\n", check_path=relative_path)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    "header",
    [
        "--- /dev/null\n+++ b/link.py\nnew file mode 120000\n",
        "GIT binary patch\n",
        "diff --git a/a.py b/b.py\nsimilarity index 100%\nrename from a.py\nrename to b.py\n",
        "diff --git a/a.py b/b.py\nsimilarity index 100%\ncopy from a.py\ncopy to b.py\n",
    ],
)
def test_apply_patch_rejects_unsafe_headers(tmp_path: Path, header: str) -> None:
    with pytest.raises(PatchError):
        apply_patch(tmp_path, header, check_path=relative_path)


def test_final_diff_includes_created_and_deleted_text_files(tmp_path: Path) -> None:
    (tmp_path / "old.py").write_text("old\n", encoding="utf-8")
    before = snapshot_tree(tmp_path)
    (tmp_path / "old.py").unlink()
    (tmp_path / "new.py").write_text("new\n", encoding="utf-8")
    diff = build_final_diff(before, snapshot_tree(tmp_path))
    assert "--- a/old.py" in diff
    assert "+++ b/new.py" in diff
