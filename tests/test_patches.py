from pathlib import Path

import pytest

from agent.patches import PatchError, apply_patch, build_final_diff, snapshot_tree


def test_apply_patch_changes_only_declared_relative_file(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("value = 1\n", encoding="utf-8")
    changed = apply_patch(
        tmp_path,
        "--- a/a.py\n+++ b/a.py\n@@ -1 +1 @@\n-value = 1\n+value = 2\n",
    )
    assert changed == ("a.py",)
    assert (tmp_path / "a.py").read_text(encoding="utf-8") == "value = 2\n"


@pytest.mark.parametrize(
    "header",
    [
        "--- a/a.py\n+++ b/../outside.py\n",
        "--- C:/secret.py\n+++ C:/secret.py\n",
        "--- /dev/null\n+++ b/link.py\nnew file mode 120000\n",
        "GIT binary patch\n",
    ],
)
def test_apply_patch_rejects_unsafe_headers(tmp_path: Path, header: str) -> None:
    with pytest.raises(PatchError):
        apply_patch(tmp_path, header)


def test_final_diff_includes_created_and_deleted_text_files(tmp_path: Path) -> None:
    (tmp_path / "old.py").write_text("old\n", encoding="utf-8")
    before = snapshot_tree(tmp_path)
    (tmp_path / "old.py").unlink()
    (tmp_path / "new.py").write_text("new\n", encoding="utf-8")
    diff = build_final_diff(before, snapshot_tree(tmp_path))
    assert "--- a/old.py" in diff
    assert "+++ b/new.py" in diff
